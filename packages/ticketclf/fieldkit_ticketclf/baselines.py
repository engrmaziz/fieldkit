"""Classifier baselines for Halden customer support ticket triage.

Implements 4 baselines matching Milestone 1 specifications:
1. TF-IDF char 3-5 n-grams + Logistic Regression (CPU)
2. Dense Multilingual Embeddings + Logistic Regression (CPU)
3. LLM Zero-Shot via packages/llm (structured JSON schema)
4. LLM 5-Shot via nearest-neighbor exemplars from training corpus
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import numpy as np
from fieldkit_common.logging import get_logger
from fieldkit_llm import LLMClient, get_llm_client
from pydantic import BaseModel, Field, field_validator
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics.pairwise import cosine_similarity

from .data import ALLOWED_PRIORITIES, ALLOWED_QUEUES

logger = get_logger("fieldkit.ticketclf.baselines")

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
ZEROSHOT_TEMPLATE = PROMPTS_DIR / "classify_zeroshot.jinja"
FEWSHOT_TEMPLATE = PROMPTS_DIR / "classify_fewshot.jinja"


class TicketClassificationOutput(BaseModel):
    """Structured, deterministic schema for ticket classification."""

    queue: str = Field(description="Target triage queue category")
    priority: str = Field(description="Target priority level")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Classification confidence")

    @field_validator("queue", mode="before")
    @classmethod
    def validate_queue(cls, v: Any) -> str:
        s = str(v).strip().lower()
        if s in ALLOWED_QUEUES:
            return s
        return "other"

    @field_validator("priority", mode="before")
    @classmethod
    def validate_priority(cls, v: Any) -> str:
        s = str(v).strip().lower()
        if s in ALLOWED_PRIORITIES:
            return s
        return "medium"

    @field_validator("confidence", mode="before")
    @classmethod
    def validate_confidence(cls, v: Any) -> float:
        try:
            val = float(v)
            return max(0.0, min(1.0, val))
        except (ValueError, TypeError):
            return 0.5


class BaseClassifier:
    """Base interface for ticket triage baselines."""

    name: str = "base"

    def fit(self, train_records: list[dict[str, Any]]) -> None:
        """Fit baseline model on training set."""
        pass

    async def fit_async(self, train_records: list[dict[str, Any]]) -> None:
        """Async fit wrapper."""
        self.fit(train_records)

    def predict_one(self, text: str, language: str = "en") -> TicketClassificationOutput:
        """Synchronously classify a single ticket."""
        raise NotImplementedError

    async def predict_async(self, text: str, language: str = "en") -> TicketClassificationOutput:
        """Asynchronously classify a single ticket."""
        return self.predict_one(text, language)

    def predict_batch(self, records: list[dict[str, Any]]) -> list[TicketClassificationOutput]:
        """Classify a batch of records synchronously."""
        return [self.predict_one(r.get("text", ""), r.get("language", "en")) for r in records]

    async def predict_batch_async(
        self, records: list[dict[str, Any]]
    ) -> list[TicketClassificationOutput]:
        """Classify a batch of records asynchronously."""
        results: list[TicketClassificationOutput] = []
        for r in records:
            res = await self.predict_async(r.get("text", ""), r.get("language", "en"))
            results.append(res)
        return results


class TfidfBaseline(BaseClassifier):
    """Baseline (a): Char 3-5 n-grams + Logistic Regression (CPU).

    Excels at multilingual technical German compounds and English terminology.
    """

    name: str = "tfidf_logreg"

    def __init__(self, seed: int = 42) -> None:
        self.seed = seed
        self.vectorizer = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(3, 5),
            min_df=2,
            max_features=25000,
            sublinear_tf=True,
        )
        self.queue_clf = LogisticRegression(
            max_iter=1000,
            C=1.0,
            random_state=seed,
        )
        self.priority_clf = LogisticRegression(
            max_iter=1000,
            C=1.0,
            random_state=seed,
        )
        self._is_fitted: bool = False

    def fit(self, train_records: list[dict[str, Any]]) -> None:
        texts = [r.get("text", "") for r in train_records]
        queues = [r.get("queue", "other") for r in train_records]
        priorities = [r.get("priority", "medium") for r in train_records]

        x_feat = self.vectorizer.fit_transform(texts)
        self.queue_clf.fit(x_feat, queues)
        self.priority_clf.fit(x_feat, priorities)
        self._is_fitted = True

    def predict_one(self, text: str, language: str = "en") -> TicketClassificationOutput:
        if not self._is_fitted:
            raise RuntimeError("TfidfBaseline must be fitted before predict.")

        x_feat = self.vectorizer.transform([text])
        q_probs = self.queue_clf.predict_proba(x_feat)[0]
        q_idx = int(np.argmax(q_probs))
        q_label = str(self.queue_clf.classes_[q_idx])
        confidence = float(q_probs[q_idx])

        p_label = str(self.priority_clf.predict(x_feat)[0])

        return TicketClassificationOutput(
            queue=q_label,
            priority=p_label,
            confidence=round(confidence, 4),
        )


class DenseEmbeddingBaseline(BaseClassifier):
    """Baseline (b): Dense Multilingual Embeddings + Logistic Regression (CPU).

    Uses local embeddings via LLMClient (nomic-embed-text or offline fallback).
    """

    name: str = "dense_embed_logreg"

    def __init__(self, client: LLMClient | None = None, seed: int = 42) -> None:
        self.client = client or get_llm_client()
        self.seed = seed
        self.queue_clf = LogisticRegression(
            max_iter=1000,
            C=1.0,
            random_state=seed,
        )
        self.priority_clf = LogisticRegression(
            max_iter=1000,
            C=1.0,
            random_state=seed,
        )
        self._is_fitted: bool = False

    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        # Batch into slices of 50 to avoid overloading local embedding server
        batch_size = 50
        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            chunk = texts[i : i + batch_size]
            emb = await self.client.embed(chunk, is_query=False, task="ticketclf_embed")
            all_embeddings.extend(emb)
        return all_embeddings

    async def fit_async(self, train_records: list[dict[str, Any]]) -> None:
        texts = [r.get("text", "") for r in train_records]
        queues = [r.get("queue", "other") for r in train_records]
        priorities = [r.get("priority", "medium") for r in train_records]

        embeddings = await self._embed_batch(texts)
        x_mat = np.array(embeddings, dtype=np.float32)

        self.queue_clf.fit(x_mat, queues)
        self.priority_clf.fit(x_mat, priorities)
        self._is_fitted = True

    def fit(self, train_records: list[dict[str, Any]]) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # If in an event loop, create a task or run via nestable logic
            asyncio.run_coroutine_threadsafe(self.fit_async(train_records), loop).result()
        else:
            asyncio.run(self.fit_async(train_records))

    async def predict_async(self, text: str, language: str = "en") -> TicketClassificationOutput:
        if not self._is_fitted:
            raise RuntimeError("DenseEmbeddingBaseline must be fitted before predict.")

        embs = await self.client.embed([text], is_query=False, task="ticketclf_embed")
        x_vec = np.array(embs, dtype=np.float32)

        q_probs = self.queue_clf.predict_proba(x_vec)[0]
        q_idx = int(np.argmax(q_probs))
        q_label = str(self.queue_clf.classes_[q_idx])
        confidence = float(q_probs[q_idx])

        p_label = str(self.priority_clf.predict(x_vec)[0])

        return TicketClassificationOutput(
            queue=q_label,
            priority=p_label,
            confidence=round(confidence, 4),
        )

    def predict_one(self, text: str, language: str = "en") -> TicketClassificationOutput:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            return asyncio.run_coroutine_threadsafe(
                self.predict_async(text, language), loop
            ).result()
        return asyncio.run(self.predict_async(text, language))


class LLMZeroShotBaseline(BaseClassifier):
    """Baseline (c): LLM Zero-Shot with structured Pydantic schema validation."""

    name: str = "llm_zero_shot"

    def __init__(self, client: LLMClient | None = None, model: str | None = None) -> None:
        self.client = client or get_llm_client()
        self.model = model

    async def predict_async(self, text: str, language: str = "en") -> TicketClassificationOutput:
        try:
            out = await self.client.structured_output_from_template(
                template_path=ZEROSHOT_TEMPLATE,
                template_vars={"ticket_text": text, "language": language},
                response_model=TicketClassificationOutput,
                task="p3_clf_zeroshot",
                model=self.model,
                temperature=0.0,
                seed=42,
            )
            return out
        except Exception as exc:
            logger.warning("llm_zeroshot_fallback_on_error", error=str(exc))
            return TicketClassificationOutput(queue="other", priority="medium", confidence=0.0)

    def predict_one(self, text: str, language: str = "en") -> TicketClassificationOutput:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            return asyncio.run_coroutine_threadsafe(
                self.predict_async(text, language), loop
            ).result()
        return asyncio.run(self.predict_async(text, language))


class LLMFewShotBaseline(BaseClassifier):
    """Baseline (d): LLM 5-Shot with nearest-neighbor exemplars from training corpus."""

    name: str = "llm_few_shot"

    def __init__(
        self,
        client: LLMClient | None = None,
        model: str | None = None,
        n_neighbors: int = 5,
    ) -> None:
        self.client = client or get_llm_client()
        self.model = model
        self.n_neighbors = n_neighbors
        self.vectorizer = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(3, 5),
            min_df=2,
            max_features=15000,
        )
        self.train_records: list[dict[str, Any]] = []
        self._train_features: Any = None
        self._is_fitted: bool = False

    def fit(self, train_records: list[dict[str, Any]]) -> None:
        self.train_records = list(train_records)
        texts = [r.get("text", "") for r in self.train_records]
        self._train_features = self.vectorizer.fit_transform(texts)
        self._is_fitted = True

    def _get_exemplars(self, text: str) -> list[dict[str, Any]]:
        if not self._is_fitted or not self.train_records:
            return []

        x_query = self.vectorizer.transform([text])
        sims = cosine_similarity(x_query, self._train_features)[0]
        top_indices = np.argsort(sims)[::-1][: self.n_neighbors]

        exemplars: list[dict[str, Any]] = []
        for idx in top_indices:
            rec = self.train_records[int(idx)]
            exemplars.append(
                {
                    "text": rec.get("text", "")[:300].strip(),
                    "queue": rec.get("queue", "other"),
                    "priority": rec.get("priority", "medium"),
                }
            )
        return exemplars

    async def predict_async(self, text: str, language: str = "en") -> TicketClassificationOutput:
        exemplars = self._get_exemplars(text)
        try:
            out = await self.client.structured_output_from_template(
                template_path=FEWSHOT_TEMPLATE,
                template_vars={
                    "ticket_text": text,
                    "language": language,
                    "exemplars": exemplars,
                },
                response_model=TicketClassificationOutput,
                task="p3_clf_fewshot",
                model=self.model,
                temperature=0.0,
                seed=42,
            )
            return out
        except Exception as exc:
            logger.warning("llm_fewshot_fallback_on_error", error=str(exc))
            return TicketClassificationOutput(queue="other", priority="medium", confidence=0.0)

    def predict_one(self, text: str, language: str = "en") -> TicketClassificationOutput:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            return asyncio.run_coroutine_threadsafe(
                self.predict_async(text, language), loop
            ).result()
        return asyncio.run(self.predict_async(text, language))
