"""Unit and integration tests for permission-aware hybrid retrieval and cross-encoder reranking."""

import pytest
from fieldkit_common.auth import Principal
from fieldkit_retrieval.hybrid import HybridSearchEngine, compute_rrf_score
from fieldkit_retrieval.models import ProcessedChunk
from fieldkit_retrieval.rerank import CrossEncoderReranker


@pytest.fixture
def sample_chunks() -> list[ProcessedChunk]:
    return [
        ProcessedChunk(
            chunk_id="chunk-legal-001",
            doc_id="doc-legal",
            chunk_index=0,
            heading_path=["Confidential Legal", "Section 1", "Arbitration"],
            content="Arbitration clause for supplier contract disputes under DIS rules in Frankfurt.",
            token_count=85,
            language="en",
            tsv_config="english",
            allowed_roles=["admin", "legal"],
            allowed_plants=None,
        ),
        ProcessedChunk(
            chunk_id="chunk-ham-quality-002",
            doc_id="doc-ham",
            chunk_index=0,
            heading_path=["Plant Hamburg", "Assembly Line 4", "Honing"],
            content="Honing surface roughness Ra 0.20 to 0.40 um for hydraulic cylinder barrels in Hamburg DE-HAM.",
            token_count=92,
            language="en",
            tsv_config="english",
            allowed_roles=["admin", "quality"],
            allowed_plants=["DE-HAM"],
        ),
        ProcessedChunk(
            chunk_id="chunk-str-support-003",
            doc_id="doc-str",
            chunk_index=0,
            heading_path=["Plant Stuttgart", "Maintenance", "Accumulators"],
            content="Hydraulic accumulator bladder replacement procedure for plant Stuttgart DE-STR assembly line.",
            token_count=88,
            language="en",
            tsv_config="english",
            allowed_roles=["admin", "support"],
            allowed_plants=["DE-STR"],
        ),
        ProcessedChunk(
            chunk_id="chunk-global-sop-004",
            doc_id="doc-global",
            chunk_index=0,
            heading_path=["Global SOP", "General", "PPE"],
            content="Personal protective equipment required: EN 388 nitrile gloves and EN 166 safety goggles.",
            token_count=70,
            language="en",
            tsv_config="english",
            allowed_roles=["admin", "quality", "support", "legal"],
            allowed_plants=None,
        ),
        ProcessedChunk(
            chunk_id="chunk-de-regulation-005",
            doc_id="doc-eu-de",
            chunk_index=0,
            heading_path=["EU Maschinenverordnung", "Anhang III", "Schutzhauben"],
            content="Trennende Schutzeinrichtungen für hydraulische Hochdruckventile und Sicherheitsbauteile.",
            token_count=75,
            language="de",
            tsv_config="german",
            allowed_roles=["admin", "quality", "support", "legal"],
            allowed_plants=None,
        ),
    ]


@pytest.fixture
def search_engine(sample_chunks: list[ProcessedChunk]) -> HybridSearchEngine:
    engine = HybridSearchEngine(k_rrf=60)
    engine.load_in_memory_index(sample_chunks)
    return engine


def test_rrf_score_math() -> None:
    """Verify Reciprocal Rank Fusion formula: 1/(k + rank_a) + 1/(k + rank_b)."""
    # Item ranked #1 in both lists (rank 1): 1/61 + 1/61 = 2/61 ~ 0.03278688
    score_both_first = compute_rrf_score(rank_bm25=1, rank_vector=1, k=60)
    assert pytest.approx(score_both_first, 0.0001) == (1 / 61) + (1 / 61)

    # Item ranked #1 in BM25 only: 1/61 + 0 = 1/61 ~ 0.01639344
    score_bm25_only = compute_rrf_score(rank_bm25=1, rank_vector=None, k=60)
    assert pytest.approx(score_bm25_only, 0.0001) == 1 / 61

    # Item ranked #5 in BM25 and #2 in Vector: 1/65 + 1/62
    score_mixed = compute_rrf_score(rank_bm25=5, rank_vector=2, k=60)
    assert pytest.approx(score_mixed, 0.0001) == (1 / 65) + (1 / 62)


@pytest.mark.asyncio
async def test_permission_filtering_legal_persona(search_engine: HybridSearchEngine) -> None:
    """Verify that Sofia (legal, global) sees legal + global documents, but never plant-specific."""
    sofia = Principal(sub="sofia-01", username="sofia", roles=["legal"], plant="PL-WRO")
    results = await search_engine.search("disputes and honing and PPE", principal=sofia, k=10)

    chunk_ids = [r.chunk_id for r in results]
    assert "chunk-legal-001" in chunk_ids
    assert "chunk-global-sop-004" in chunk_ids
    # Must NOT see Hamburg or Stuttgart plant production chunks
    assert "chunk-ham-quality-002" not in chunk_ids
    assert "chunk-str-support-003" not in chunk_ids


@pytest.mark.asyncio
async def test_permission_filtering_plant_quality_persona(search_engine: HybridSearchEngine) -> None:
    """Verify that Mehmet (quality, DE-HAM) sees Hamburg chunks and global chunks, but never legal or Stuttgart."""
    mehmet = Principal(sub="mehmet-01", username="mehmet", roles=["quality"], plant="DE-HAM")
    results = await search_engine.search("honing and pressure and legal", principal=mehmet, k=10)

    chunk_ids = [r.chunk_id for r in results]
    assert "chunk-ham-quality-002" in chunk_ids
    assert "chunk-global-sop-004" in chunk_ids
    # Zero cross-plant or restricted legal leaks
    assert "chunk-legal-001" not in chunk_ids
    assert "chunk-str-support-003" not in chunk_ids


@pytest.mark.asyncio
async def test_permission_filtering_admin_persona(search_engine: HybridSearchEngine) -> None:
    """Verify that Jana (admin, Global) has visibility across all plants and restricted legal chunks."""
    jana = Principal(sub="jana-01", username="jana", roles=["admin"], plant=None)
    results = await search_engine.search("procedure", principal=jana, k=10)

    chunk_ids = [r.chunk_id for r in results]
    assert "chunk-legal-001" in chunk_ids
    assert "chunk-ham-quality-002" in chunk_ids
    assert "chunk-str-support-003" in chunk_ids
    assert "chunk-global-sop-004" in chunk_ids


@pytest.mark.asyncio
async def test_reranker_stage_scores_and_ordering() -> None:
    """Verify that reranker emits all scoring stages for OpenTelemetry tracing and evaluation."""
    reranker = CrossEncoderReranker(enabled=True)
    query = "hydraulic cylinder honing surface roughness"
    passages = [
        ("chunk-1", "Standard operating procedure for hydraulic valve safety."),
        ("chunk-2", "Honing surface roughness Ra 0.20 to 0.40 um for hydraulic cylinder barrels in Hamburg."),
        ("chunk-3", "General personnel protective equipment guidelines."),
    ]

    scored = await reranker.rerank(query=query, candidate_passages=passages, top_k=2)
    assert len(scored) == 2
    # The passage with exact terminology "honing surface roughness" must rank first
    assert scored[0].chunk_id == "chunk-2"
    assert scored[0].final_rank == 1
    assert scored[0].rerank_score > scored[1].rerank_score
