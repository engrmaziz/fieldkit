"""Local GPU Training and ONNX Export Script for Project 3 (Ops Copilot).

Trains a multi-task XLM-RoBERTa model on local NVIDIA GPU (RTX 3090),
calibrates temperature scaling, exports to ONNX, quantizes to Int8,
and saves deployment-ready artifacts directly to models/p3/.
"""

from __future__ import annotations

import json
import random
import time
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import onnxruntime as ort
import pandas as pd
import torch
import torch.nn as nn
from onnxruntime.quantization import QuantType as WeightType
from onnxruntime.quantization import quantize_dynamic
from scipy.optimize import minimize_scalar
from sklearn.metrics import accuracy_score, f1_score
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModel, AutoTokenizer, get_linear_schedule_with_warmup

# 1. Constants and Taxonomies
ALLOWED_QUEUES = [
    "technical_defect",
    "order_delivery",
    "returns_rma",
    "billing_inquiry",
    "general_inquiry",
    "other",
]

ALLOWED_PRIORITIES = [
    "low",
    "medium",
    "high",
    "critical",
]

SEED = 42
MODEL_NAME = "xlm-roberta-base"
MAX_LEN = 256
BATCH_SIZE = 16
EPOCHS = 3
LR = 2e-5
WARMUP_RATIO = 0.10


def set_seed(seed: int = 42) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


class TicketDataset(Dataset):
    """PyTorch Dataset for multi-task support ticket classification."""

    def __init__(
        self,
        df: pd.DataFrame,
        tokenizer: Any,
        queue2id: dict[str, int],
        priority2id: dict[str, int],
        max_len: int = 256,
    ) -> None:
        self.texts = df["text"].tolist()
        self.queues = [queue2id.get(q, queue2id["other"]) for q in df["queue"]]
        self.priorities = [priority2id.get(p, priority2id["medium"]) for p in df["priority"]]
        self.languages = df["language"].tolist() if "language" in df.columns else ["en"] * len(df)
        self.tokenizer = tokenizer
        self.max_len = max_len

    def __len__(self) -> int:
        return len(self.texts)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        enc = self.tokenizer(
            self.texts[idx],
            padding="max_length",
            truncation=True,
            max_length=self.max_len,
            return_tensors="pt",
        )
        return {
            "input_ids": enc["input_ids"].squeeze(0),
            "attention_mask": enc["attention_mask"].squeeze(0),
            "queue_label": torch.tensor(self.queues[idx], dtype=torch.long),
            "priority_label": torch.tensor(self.priorities[idx], dtype=torch.long),
        }


class MultiTaskXLMRoberta(nn.Module):
    """Shared XLM-RoBERTa encoder with dual classification heads."""

    def __init__(
        self,
        model_name: str,
        num_queues: int = 6,
        num_priorities: int = 4,
        dropout: float = 0.2,
    ) -> None:
        super().__init__()
        self.encoder = AutoModel.from_pretrained(model_name)
        hidden_size = self.encoder.config.hidden_size
        self.dropout = nn.Dropout(dropout)
        self.queue_head = nn.Linear(hidden_size, num_queues)
        self.priority_head = nn.Linear(hidden_size, num_priorities)

    def forward(
        self, input_ids: torch.Tensor, attention_mask: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor]:
        outputs = self.encoder(input_ids=input_ids, attention_mask=attention_mask)
        token_embeddings = outputs[0]
        mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        sum_embeddings = torch.sum(token_embeddings * mask_expanded, 1)
        sum_mask = torch.clamp(mask_expanded.sum(1), min=1e-9)
        pooled = sum_embeddings / sum_mask
        pooled = self.dropout(pooled)

        queue_logits = self.queue_head(pooled)
        priority_logits = self.priority_head(pooled)
        return queue_logits, priority_logits


def softmax_np(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - np.max(x, axis=-1, keepdims=True))
    return e / np.sum(e, axis=-1, keepdims=True)


def nll_opt(t: float, logits: np.ndarray, labels: np.ndarray) -> float:
    probs = softmax_np(logits / max(t, 1e-4))
    n = len(labels)
    return -float(np.mean(np.log(np.clip(probs[np.arange(n), labels], 1e-12, 1.0))))


def main() -> None:
    set_seed(SEED)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("=" * 70)
    print("FIELDKIT PROJECT 3: LOCAL MULTI-TASK XLM-R FINE-TUNING & ONNX EXPORT")
    print(f"[*] Compute Device: {device}")
    if torch.cuda.is_available():
        print(f"[*] GPU Model:     {torch.cuda.get_device_name(0)}")
        print(f"[*] VRAM Total:    {torch.cuda.get_device_properties(0).total_memory / (1024**3):.1f} GB")
    print("=" * 70)

    repo_root = Path(__file__).resolve().parent.parent
    data_dir = repo_root / "data" / "p3"
    models_dir = repo_root / "models" / "p3"
    models_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load Parquet splits
    train_path = data_dir / "train.parquet"
    val_path = data_dir / "val.parquet"
    test_path = data_dir / "test.parquet"

    print(f"[*] Loading training splits from {data_dir}...")
    train_df = pd.read_parquet(train_path)
    val_df = pd.read_parquet(val_path)
    test_df = pd.read_parquet(test_path)

    print(f"[+] Train: {len(train_df)} rows | Val: {len(val_df)} rows | Test: {len(test_df)} rows")

    queue2id = {q: i for i, q in enumerate(ALLOWED_QUEUES)}
    id2queue = dict(enumerate(ALLOWED_QUEUES))
    priority2id = {p: i for i, p in enumerate(ALLOWED_PRIORITIES)}
    id2priority = dict(enumerate(ALLOWED_PRIORITIES))

    # Compute class weights to balance CrossEntropyLoss
    q_counts = train_df["queue"].map(queue2id).value_counts().sort_index()
    q_weights_arr = [len(train_df) / (len(ALLOWED_QUEUES) * max(q_counts.get(i, 1), 1)) for i in range(len(ALLOWED_QUEUES))]
    q_weights = torch.tensor(q_weights_arr, dtype=torch.float32).to(device)

    p_counts = train_df["priority"].map(priority2id).value_counts().sort_index()
    p_weights_arr = [len(train_df) / (len(ALLOWED_PRIORITIES) * max(p_counts.get(i, 1), 1)) for i in range(len(ALLOWED_PRIORITIES))]
    p_weights = torch.tensor(p_weights_arr, dtype=torch.float32).to(device)

    # 2. Tokenizer & Datasets
    print(f"[*] Loading pretrained tokenizer: {MODEL_NAME}...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

    train_ds = TicketDataset(train_df, tokenizer, queue2id, priority2id, max_len=MAX_LEN)
    val_ds = TicketDataset(val_df, tokenizer, queue2id, priority2id, max_len=MAX_LEN)

    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False)

    # 3. Model Architecture
    print(f"[*] Initializing MultiTaskXLMRoberta on {device}...")
    model = MultiTaskXLMRoberta(
        MODEL_NAME,
        num_queues=len(ALLOWED_QUEUES),
        num_priorities=len(ALLOWED_PRIORITIES),
    ).to(device)

    optimizer = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=0.01)
    total_steps = len(train_loader) * EPOCHS
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=int(total_steps * WARMUP_RATIO),
        num_training_steps=total_steps,
    )

    loss_fn_queue = nn.CrossEntropyLoss(weight=q_weights)
    loss_fn_priority = nn.CrossEntropyLoss(weight=p_weights)
    use_amp = torch.cuda.is_available()
    scaler = torch.amp.GradScaler("cuda") if use_amp else None

    # 4. Training Loop
    print(f"[*] Beginning training ({EPOCHS} epochs, batch_size={BATCH_SIZE}, fp16={use_amp})...")
    best_val_f1 = -1.0
    best_model_weights = None

    for epoch in range(1, EPOCHS + 1):
        t0 = time.time()
        model.train()
        total_train_loss = 0.0

        for batch in train_loader:
            input_ids = batch["input_ids"].to(device)
            mask = batch["attention_mask"].to(device)
            q_labels = batch["queue_label"].to(device)
            p_labels = batch["priority_label"].to(device)

            optimizer.zero_grad()
            if scaler:
                with torch.amp.autocast("cuda"):
                    q_logits, p_logits = model(input_ids, mask)
                    loss = loss_fn_queue(q_logits, q_labels) + 0.5 * loss_fn_priority(p_logits, p_labels)
                scaler.scale(loss).backward()
                scaler.step(optimizer)
                scaler.update()
            else:
                q_logits, p_logits = model(input_ids, mask)
                loss = loss_fn_queue(q_logits, q_labels) + 0.5 * loss_fn_priority(p_logits, p_labels)
                loss.backward()
                optimizer.step()

            scheduler.step()
            total_train_loss += loss.item()

        # Validation
        model.eval()
        all_q_preds, all_q_true = [], []
        with torch.no_grad():
            for batch in val_loader:
                input_ids = batch["input_ids"].to(device)
                mask = batch["attention_mask"].to(device)
                q_labels = batch["queue_label"].to(device)
                q_logits, _ = model(input_ids, mask)
                all_q_preds.extend(torch.argmax(q_logits, dim=-1).cpu().tolist())
                all_q_true.extend(q_labels.cpu().tolist())

        val_f1 = f1_score(all_q_true, all_q_preds, average="macro", zero_division=0)
        elapsed = time.time() - t0
        avg_loss = total_train_loss / len(train_loader)
        print(f"    Epoch {epoch}/{EPOCHS} [{elapsed:.1f}s] | Loss: {avg_loss:.4f} | Val Queue Macro-F1: {val_f1:.4f}")

        if val_f1 > best_val_f1:
            best_val_f1 = val_f1
            best_model_weights = {k: v.cpu().clone() for k, v in model.state_dict().items()}

    if best_model_weights is not None:
        model.load_state_dict(best_model_weights)
    print(f"[+] Restored best model weights with Val Macro-F1: {best_val_f1:.4f}")

    # 5. Post-Hoc Temperature Scaling Calibration
    print("[*] Calibrating post-hoc temperature scalers on validation set...")
    model.eval()
    val_q_logits, val_q_labels = [], []
    val_p_logits, val_p_labels = [], []

    with torch.no_grad():
        for batch in val_loader:
            input_ids = batch["input_ids"].to(device)
            mask = batch["attention_mask"].to(device)
            q_logits, p_logits = model(input_ids, mask)
            val_q_logits.append(q_logits.cpu().numpy())
            val_q_labels.append(batch["queue_label"].numpy())
            val_p_logits.append(p_logits.cpu().numpy())
            val_p_labels.append(batch["priority_label"].numpy())

    val_q_logits_arr = np.concatenate(val_q_logits, axis=0)
    val_q_labels_arr = np.concatenate(val_q_labels, axis=0)
    val_p_logits_arr = np.concatenate(val_p_logits, axis=0)
    val_p_labels_arr = np.concatenate(val_p_labels, axis=0)

    res_q = minimize_scalar(nll_opt, args=(val_q_logits_arr, val_q_labels_arr), bounds=(0.05, 10.0), method="bounded")
    res_p = minimize_scalar(nll_opt, args=(val_p_logits_arr, val_p_labels_arr), bounds=(0.05, 10.0), method="bounded")

    temp_q = round(float(res_q.x), 4)
    temp_p = round(float(res_p.x), 4)
    print(f"[+] Calibrated Scalers: Queue T={temp_q}, Priority T={temp_p}")

    # 6. Export to ONNX
    print("[*] Exporting multi-task model to ONNX...")
    onnx_path = models_dir / "model.onnx"
    dummy_ids = torch.zeros((1, MAX_LEN), dtype=torch.long, device=device)
    dummy_mask = torch.ones((1, MAX_LEN), dtype=torch.long, device=device)

    model.eval()
    torch.onnx.export(
        model,
        (dummy_ids, dummy_mask),
        str(onnx_path),
        input_names=["input_ids", "attention_mask"],
        output_names=["queue_logits", "priority_logits"],
        dynamic_axes={
            "input_ids": {0: "batch_size", 1: "sequence_length"},
            "attention_mask": {0: "batch_size", 1: "sequence_length"},
            "queue_logits": {0: "batch_size"},
            "priority_logits": {0: "batch_size"},
        },
        opset_version=14,
    )
    onnx_size_mb = onnx_path.stat().st_size / (1024 * 1024)
    print(f"[+] Exported Float32 ONNX model ({onnx_size_mb:.2f} MB) -> {onnx_path}")

    # 7. Dynamic Int8 Quantization
    print("[*] Performing dynamic Int8 quantization with ONNX Runtime...")
    quant_path = models_dir / "model_int8.onnx"
    quantize_dynamic(
        model_input=str(onnx_path),
        model_output=str(quant_path),
        weight_type=WeightType.QInt8,
    )
    quant_size_mb = quant_path.stat().st_size / (1024 * 1024)
    print(f"[+] Quantized Int8 ONNX model ({quant_size_mb:.2f} MB) -> {quant_path}")

    # 8. Test Set Evaluation & Latency Benchmark on 4-Core CPU
    print("[*] Benchmarking quantized Int8 ONNX model on test set (CPU Provider, 4 threads)...")
    sess_options = ort.SessionOptions()
    sess_options.intra_op_num_threads = 4
    ort_sess = ort.InferenceSession(str(quant_path), sess_options, providers=["CPUExecutionProvider"])

    test_latencies = []
    all_q_preds, all_p_preds = [], []

    for _, row in test_df.iterrows():
        t_start = time.perf_counter()
        enc = tokenizer(row["text"], max_length=MAX_LEN, padding="max_length", truncation=True, return_tensors="np")
        feeds = {"input_ids": enc["input_ids"], "attention_mask": enc["attention_mask"]}
        q_logits_out, p_logits_out = ort_sess.run(None, feeds)
        calib_q = softmax_np(q_logits_out / temp_q)[0]
        calib_p = softmax_np(p_logits_out / temp_p)[0]
        lat_ms = (time.perf_counter() - t_start) * 1000.0
        test_latencies.append(lat_ms)

        all_q_preds.append(id2queue[int(np.argmax(calib_q))])
        all_p_preds.append(id2priority[int(np.argmax(calib_p))])

    test_df_eval = test_df.copy()
    test_df_eval["pred_queue"] = all_q_preds
    test_df_eval["pred_priority"] = all_p_preds

    overall_q_f1 = f1_score(test_df_eval["queue"], test_df_eval["pred_queue"], average="macro", zero_division=0)
    en_mask = test_df_eval["language"] == "en"
    de_mask = test_df_eval["language"] == "de"
    en_q_f1 = f1_score(test_df_eval.loc[en_mask, "queue"], test_df_eval.loc[en_mask, "pred_queue"], average="macro", zero_division=0)
    de_q_f1 = f1_score(test_df_eval.loc[de_mask, "queue"], test_df_eval.loc[de_mask, "pred_queue"], average="macro", zero_division=0)
    acc = accuracy_score(test_df_eval["queue"], test_df_eval["pred_queue"])

    p50 = float(np.percentile(test_latencies, 50))
    p95 = float(np.percentile(test_latencies, 95))

    print("=" * 70)
    print("PROJECT 3: XLM-R ONNX INT8 LOCAL EVALUATION REPORT")
    print(f"[*] Queue Macro-F1 Overall: {overall_q_f1:.4f} (Target: >= 0.85)")
    print(f"[*] Queue Macro-F1 EN:      {en_q_f1:.4f}")
    print(f"[*] Queue Macro-F1 DE:      {de_q_f1:.4f} (Target: >= 0.82)")
    print(f"[*] Queue Accuracy:         {acc*100:.2f}%")
    print(f"[*] CPU Latency P50:        {p50:.2f} ms")
    print(f"[*] CPU Latency P95:        {p95:.2f} ms (Target: < 30.0 ms)")
    print("=" * 70)

    # 9. Save Metadata and Tokenizer Artifacts
    print(f"[*] Saving tokenizer to {models_dir / 'tokenizer'}...")
    tokenizer.save_pretrained(str(models_dir / "tokenizer"))

    labels_meta = {
        "allowed_queues": ALLOWED_QUEUES,
        "allowed_priorities": ALLOWED_PRIORITIES,
        "queue2id": queue2id,
        "id2queue": id2queue,
        "priority2id": priority2id,
        "id2priority": id2priority,
    }
    with open(models_dir / "labels.json", "w", encoding="utf-8") as f:
        json.dump(labels_meta, f, indent=2)

    calib_meta = {
        "temperature_queue": temp_q,
        "temperature_priority": temp_p,
        "is_fitted": True,
    }
    with open(models_dir / "temperature_scaler.json", "w", encoding="utf-8") as f:
        json.dump(calib_meta, f, indent=2)

    metrics_meta = {
        "queue_macro_f1": round(overall_q_f1, 4),
        "queue_macro_f1_en": round(en_q_f1, 4),
        "queue_macro_f1_de": round(de_q_f1, 4),
        "accuracy": round(acc, 4),
        "latency_p50_ms": round(p50, 2),
        "latency_p95_ms": round(p95, 2),
        "quantized_size_mb": round(quant_size_mb, 2),
    }
    with open(models_dir / "eval_metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics_meta, f, indent=2)

    # Also generate the deployment zip
    zip_path = models_dir / "fieldkit_xlmr_onnx.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for file_path in models_dir.rglob("*"):
            if file_path.is_file() and not file_path.name.endswith(".zip"):
                z.write(file_path, arcname=file_path.relative_to(models_dir))

    print(f"[+] All artifacts successfully saved to {models_dir}!")
    print(f"[+] Bundle zip created: {zip_path} ({zip_path.stat().st_size / (1024*1024):.2f} MB)")


if __name__ == "__main__":
    main()
