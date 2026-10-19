"""Tests for Project 2 retrieval evaluation benchmark and gold dataset."""

import json
from pathlib import Path

from fieldkit_common.auth import Principal
from fieldkit_retrieval.hybrid import HybridSearchEngine
from fieldkit_retrieval.models import ProcessedChunk


def test_rag_gold_dataset_integrity() -> None:
    gold_path = Path("evals/p2/rag_gold.jsonl")
    assert gold_path.exists(), "evals/p2/rag_gold.jsonl must exist"

    items = []
    with open(gold_path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                items.append(json.loads(line))

    assert len(items) == 150, f"Expected 150 gold items, got {len(items)}"

    answerable = [item for item in items if item["answerable"]]
    unanswerable = [item for item in items if not item["answerable"]]
    german_items = [item for item in items if item["lang"] == "de"]

    assert len(answerable) == 120, f"Expected 120 answerable items, got {len(answerable)}"
    assert len(unanswerable) == 30, f"Expected 30 unanswerable items, got {len(unanswerable)}"
    assert len(german_items) >= 20, f"Expected at least 20 German items, got {len(german_items)}"

    for item in items:
        assert "id" in item
        assert "question" in item
        assert "lang" in item
        assert "relevant_chunk_ids" in item
        assert "answerable" in item
        assert "required_role" in item
        if item["answerable"]:
            assert len(item["relevant_chunk_ids"]) > 0
        else:
            assert len(item["relevant_chunk_ids"]) == 0


def test_permission_filtering_on_retrieval() -> None:
    """Verify that plant-restricted chunks cannot be retrieved by unauthorized principals."""
    chunks = [
        ProcessedChunk(
            chunk_id="chk-ham-secret",
            doc_id="doc-ham",
            chunk_index=0,
            heading_path=["Hamburg Secret Honing"],
            content="Proprietary honing process for Plant Hamburg DE-HAM hydraulic cylinders.",
            token_count=50,
            language="en",
            tsv_config="english",
            allowed_roles=["quality"],
            allowed_plants=["DE-HAM"],
        )
    ]

    engine = HybridSearchEngine(k_rrf=60)
    engine.load_in_memory_index(chunks)

    # Unauthorized principal: Lukas from Stuttgart
    lukas = Principal(sub="lukas", username="lukas", roles=["support"], plant="DE-STR")
    import asyncio

    results = asyncio.run(
        engine.search("Hamburg Secret Honing", principal=lukas, k=5, mode="hybrid_rerank")
    )
    assert len(results) == 0

    # Authorized principal: Mehmet from Hamburg
    mehmet = Principal(sub="mehmet", username="mehmet", roles=["quality"], plant="DE-HAM")
    results_auth = asyncio.run(
        engine.search("Hamburg Secret Honing", principal=mehmet, k=5, mode="hybrid_rerank")
    )
    assert len(results_auth) == 1
    assert results_auth[0].chunk_id == "chk-ham-secret"
