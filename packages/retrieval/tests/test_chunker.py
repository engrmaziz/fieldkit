"""Unit tests for structure-aware document parsing, chunking, and ACL inheritance."""

import pytest
from fieldkit_retrieval.chunker import StructureAwareChunker
from fieldkit_retrieval.lang import detect_document_language, get_tsvector_config
from fieldkit_retrieval.models import DocumentInput, DocumentType


@pytest.fixture
def chunker() -> StructureAwareChunker:
    return StructureAwareChunker(target_tokens=400, max_tokens=512, overlap_pct=0.15)


def test_chunker_respects_max_token_limit(chunker: StructureAwareChunker) -> None:
    """Verify that no emitted chunk ever exceeds the hard 512-token ceiling."""
    long_section = "Hydraulic valve assemblies require rigorous pressure calibration. " * 80
    doc = DocumentInput(
        title="Halden Hydraulic Valve Calibration Protocol",
        doc_type=DocumentType.SOP,
        source_url="internal://sop/valve-calib.html",
        content=f"<h1>Calibration</h1><h2>Valve High Pressure</h2><p>{long_section}</p>",
        allowed_roles=["admin", "quality"],
        allowed_plants=["DE-HAM"],
    )
    chunks = chunker.chunk_document(doc)
    assert len(chunks) >= 2
    for chunk in chunks:
        assert chunk.token_count <= 512, f"Chunk exceeded 512 tokens: {chunk.token_count}"
        assert len(chunk.content.strip()) > 0


def test_heading_path_preservation_and_breadcrumbs(chunker: StructureAwareChunker) -> None:
    """Verify that hierarchical heading breadcrumbs are attached to each chunk."""
    content = """
    <h1>EU Machinery Regulation (EU) 2023/1230</h1>
    <h2>Chapter II: Obligations of Economic Operators</h2>
    <h3>Article 10: Obligations of Manufacturers</h3>
    <p>Manufacturers shall ensure machinery is designed according to essential health and safety requirements.</p>
    """
    doc = DocumentInput(
        title="EU Machinery Regulation 2023/1230",
        doc_type=DocumentType.REGULATION,
        source_url="https://eur-lex.europa.eu/eli/reg/2023/1230/oj",
        content=content,
        allowed_roles=["admin", "quality", "legal"],
        allowed_plants=None,
    )
    chunks = chunker.chunk_document(doc)
    assert len(chunks) >= 1
    chunk = chunks[0]
    expected_path = [
        "EU Machinery Regulation 2023/1230",
        "EU Machinery Regulation (EU) 2023/1230",
        "Chapter II: Obligations of Economic Operators",
        "Article 10: Obligations of Manufacturers",
    ]
    assert chunk.heading_path == expected_path
    assert "Article 10: Obligations of Manufacturers" in chunk.content


def test_markdown_table_remains_intact_without_row_splits(chunker: StructureAwareChunker) -> None:
    """Verify that tables are preserved as complete markdown blocks without split rows."""
    table_markdown = """
    | Valve Model | Nominal Pressure (bar) | Max Flow (L/min) | Seal Material | Inspection Interval |
    | :--- | :--- | :--- | :--- | :--- |
    | HV-200-A | 250 | 120 | FKM (Viton) | 500 operating hours |
    | HV-200-B | 315 | 160 | NBR (Nitrile) | 400 operating hours |
    | HV-350-Pro | 350 | 220 | PTFE Composite | 750 operating hours |
    | HV-400-HD | 420 | 300 | Metal-to-Metal | 1000 operating hours |
    """
    html_content = f"<h1>Technical Specs</h1><p>Standard specifications table:</p>{table_markdown}"
    doc = DocumentInput(
        title="High Pressure Valve Specifications",
        doc_type=DocumentType.STANDARD,
        source_url="internal://specs/valves.html",
        content=html_content,
        allowed_roles=["admin", "quality", "support"],
        allowed_plants=["DE-HAM", "DE-STR"],
    )
    chunks = chunker.chunk_document(doc)
    assert len(chunks) >= 1
    # Check that table lines are present in the chunk
    table_chunk = next((c for c in chunks if "HV-400-HD" in c.content), None)
    assert table_chunk is not None
    assert "| HV-200-A |" in table_chunk.content
    assert "| HV-400-HD |" in table_chunk.content


def test_acl_inheritance_from_document_to_chunks(chunker: StructureAwareChunker) -> None:
    """Verify that chunks faithfully inherit allowed_roles and allowed_plants from parent document."""
    doc = DocumentInput(
        title="Confidential Supplier Dispute & Patent Audit",
        doc_type=DocumentType.POLICY,
        source_url="internal://legal/patents/audit-2026.html",
        content="<h1>Confidential Legal Audit</h1><p>Restricted to legal council and executive administration.</p>",
        allowed_roles=["admin", "legal"],
        allowed_plants=["DE-HAM"],
    )
    chunks = chunker.chunk_document(doc)
    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.allowed_roles == ["admin", "legal"]
    assert chunk.allowed_plants == ["DE-HAM"]


def test_language_detection_and_tsvector_config() -> None:
    """Verify language detection across German, English, and Polish technical excerpts."""
    de_text = (
        "Die hydraulische Sicherheitsprüfung für Druckventile muss gemäß DIN EN ISO 4413 "
        "bei einer Prüftemperatur von mindestens fünfzig Grad Celsius durchgeführt werden."
    )
    en_text = (
        "Hydraulic safety inspections for pressure valves must comply with OSHA standard 1910.212 "
        "and Machinery Directive essential health and safety requirements."
    )
    pl_text = (
        "Kontrola techniczna zaworów hydraulicznych w zakładzie produkcyjnym we Wrocławiu "
        "wymaga zachowania procedur bezpieczeństwa pracy oraz atestów jakościowych."
    )

    assert detect_document_language(de_text) == "de"
    assert get_tsvector_config("de") == "german"

    assert detect_document_language(en_text) == "en"
    assert get_tsvector_config("en") == "english"

    assert detect_document_language(pl_text) == "pl"
    assert get_tsvector_config("pl") == "simple"


def test_idempotent_chunk_generation(chunker: StructureAwareChunker) -> None:
    """Verify that chunking the identical document twice produces identical chunk hashes."""
    doc = DocumentInput(
        title="Plant Hamburg Casting SOP",
        doc_type=DocumentType.SOP,
        source_url="internal://sop/de-ham/casting.html",
        content="<h1>Casting Line 4</h1><p>Safety procedures for molten alloy pouring.</p>",
        allowed_roles=["admin", "quality"],
        allowed_plants=["DE-HAM"],
    )
    run_1 = chunker.chunk_document(doc)
    run_2 = chunker.chunk_document(doc)

    assert len(run_1) == len(run_2)
    for c1, c2 in zip(run_1, run_2, strict=True):
        assert c1.chunk_id == c2.chunk_id
        assert c1.content == c2.content
        assert c1.token_count == c2.token_count


def test_html_table_element_parsed_to_markdown(chunker: StructureAwareChunker) -> None:
    """Verify that native HTML table tags are parsed into intact markdown tables."""
    html_with_table = """
    <html>
      <body>
        <h1>Halden Testing Standards</h1>
        <table border="1">
          <thead>
            <tr><th>Component</th><th>Tolerance (mm)</th><th>Test Status</th></tr>
          </thead>
          <tbody>
            <tr><td>Cylinder Head</td><td>±0.005</td><td>Passed</td></tr>
            <tr><td>Piston Ring</td><td>±0.002</td><td>Passed</td></tr>
          </tbody>
        </table>
      </body>
    </html>
    """
    doc = DocumentInput(
        title="Halden Quality Standards",
        doc_type=DocumentType.STANDARD,
        source_url="internal://quality/tolerances.html",
        content=html_with_table,
        allowed_roles=["admin", "quality"],
        allowed_plants=["DE-HAM"],
    )
    chunks = chunker.chunk_document(doc)
    assert len(chunks) >= 1
    table_chunk = next((c for c in chunks if "Cylinder Head" in c.content), None)
    assert table_chunk is not None
    assert "| Component | Tolerance (mm) | Test Status |" in table_chunk.content
    assert "| Cylinder Head | ±0.005 | Passed |" in table_chunk.content


def test_sentence_overlap_across_chunks(chunker: StructureAwareChunker) -> None:
    """Verify that when a large section splits into multiple chunks, sentence overlap is present."""
    sentences = [
        f"Safety procedure step {i}: verify hydraulic pressure before operating."
        for i in range(1, 40)
    ]
    body_text = " ".join(sentences)
    doc = DocumentInput(
        title="High Pressure Operating Procedures",
        doc_type=DocumentType.SOP,
        source_url="internal://sop/pressure.md",
        content=f"# Operating Protocol\n\n{body_text}",
        allowed_roles=["admin", "quality"],
    )
    chunks = chunker.chunk_document(doc)
    assert len(chunks) >= 2
    # Check that the beginning of chunk 1 shares text with the end of chunk 0
    chunk_0_text = chunks[0].content
    chunk_1_text = chunks[1].content
    # Find at least one sentence from chunk 0 that also appears in chunk 1
    shared = False
    for sent in sentences:
        if sent in chunk_0_text and sent in chunk_1_text:
            shared = True
            break
    assert shared, "Expected sentence overlap between adjacent chunks"
