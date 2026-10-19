"""Batched and resumable document embedding indexer."""

import json
from collections.abc import Sequence
from pathlib import Path

from fieldkit_llm.client import get_llm_client

from fieldkit_retrieval.models import ProcessedChunk


class BatchIndexer:
    """Manages batched, resumable embeddings generation for processed chunks."""

    def __init__(self, checkpoint_path: Path | str = "data/raw/corpus/embeddings_checkpoint.json") -> None:
        self.checkpoint_path = Path(checkpoint_path)
        self.llm_client = get_llm_client()
        self._cached_embeddings: dict[str, list[float]] = {}
        self._load_checkpoint()

    def _load_checkpoint(self) -> None:
        if self.checkpoint_path.exists():
            try:
                with open(self.checkpoint_path, encoding="utf-8") as f:
                    self._cached_embeddings = json.load(f)
            except Exception:
                self._cached_embeddings = {}

    def _save_checkpoint(self) -> None:
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.checkpoint_path, "w", encoding="utf-8") as f:
            json.dump(self._cached_embeddings, f)

    async def index_chunks(
        self,
        chunks: Sequence[ProcessedChunk],
        batch_size: int = 64,
    ) -> dict[str, list[float]]:
        """Compute embeddings for chunks in batches of batch_size, saving progress."""
        needed_chunks = [c for c in chunks if c.chunk_id not in self._cached_embeddings]

        for i in range(0, len(needed_chunks), batch_size):
            batch = needed_chunks[i : i + batch_size]
            texts = [c.content for c in batch]
            vectors = await self.llm_client.embed(texts, is_query=False, task="batch_index")

            for c, vec in zip(batch, vectors, strict=True):
                self._cached_embeddings[c.chunk_id] = vec

            self._save_checkpoint()

        return {c.chunk_id: self._cached_embeddings[c.chunk_id] for c in chunks if c.chunk_id in self._cached_embeddings}
