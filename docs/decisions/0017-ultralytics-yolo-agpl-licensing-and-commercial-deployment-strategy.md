# ADR 0017: Ultralytics YOLO AGPL-3.0 Licensing Implications and Commercial Deployment Strategy

- **Status**: Accepted
- **Date**: 2026-10-21
- **Author**: engrmaziz

## Context
Project 5 trains and evaluates YOLO11 detectors for industrial PPE (hard hats, safety vests) and machinery (forklifts). Ultralytics distributes its core model code under the **GNU Affero General Public License v3.0 (AGPL-3.0)**:
1. **Commercial Air-Gapped Risk**: AGPL-3.0 contains network copyleft clauses requiring that entities interacting with the software over a network receive access to the full corresponding source code. In an on-premises, air-gapped manufacturing deployment (Halden Industrie), connecting proprietary plant ontologies, ERP connectors, or custom safety rules directly to AGPL libraries introduces unacceptable legal ambiguity for enterprise legal counsel.
2. **Runtime Deployment Hygiene**: Forward-deployed production software running on edge nodes should not carry heavyweight Python training frameworks (`ultralytics`, `torch`, `torchvision`, `triton`) that consume gigabytes of disk and RAM.

## Decision

1. **Strict Decoupling of Training and Inference via ONNX**:
   - Model fine-tuning is isolated entirely within Kaggle training notebooks (`notebooks/kaggle/p5_yolo_ppe.ipynb`) or offline training runners.
   - The production serving binary (`services/vision-edge/fieldkit_vision/detector.py`) **never imports Ultralytics or PyTorch**.
   - Models are exported to standardized Open Neural Network Exchange (**ONNX**) format (opset 17, dynamic batch) and executed via Microsoft's permissive MIT-licensed **ONNX Runtime** (`onnxruntime-cpu` / `onnxruntime-gpu`).

2. **Dual-Path Commercial Deployment Strategy**:
   - **Open-Source / Portfolio Distribution**: Permissible for evaluation and open-source demonstration using the exported ONNX weights and cleanroom inference wrapper.
   - **Commercial On-Premises Customer Engagements**:
     * **Option A (Commercial License)**: Halden Industrie acquires an Ultralytics Commercial Enterprise License, waiving all AGPL-3.0 open-source distribution requirements.
     * **Option B (Permissive Apache-2.0 Drop-In Detectors)**: The `YOLOOnnxDetector` abstract interface is architected to allow zero-code-change drop-in replacement with Apache-2.0 or MIT-licensed state-of-the-art vision architectures (e.g., Baidu RT-DETR via Hugging Face Transformers, Megvii YOLOX, or ONNX-exported OpenVINO models).

## Consequences
- **Positive**: Complete legal compliance hygiene, zero viral copyleft risk for Halden's proprietary ontology and rules engine, 10x smaller container footprints (<250MB vs >4GB for full PyTorch), and seamless drop-in detector upgradeability.
- **Negative**: Dynamic post-training fine-tuning on the edge device requires exporting new ONNX checkpoints from the training pipeline rather than updating weights in-memory.
