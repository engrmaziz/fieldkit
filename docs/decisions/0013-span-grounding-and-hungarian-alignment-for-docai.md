# ADR 0013: Span-Grounded Character Alignment, Deterministic Gates, and Hungarian Bipartite Version Diffing for DocAI

- **Status**: Accepted
- **Date**: 2026-10-20
- **Author**: engrmaziz

## Context
Halden Industrie processes over 1,800 active supplier contracts and ~300 paper/scanned delivery notes daily across manufacturing plants in Hamburg, Stuttgart, and Wrocław. Unconstrained probabilistic generative extraction causes severe production hazards:
1. **Hallucination & Legal Exposure**: Free-form LLM summaries invent clause numbers, shift liability caps, or alter termination notice periods without verifiable references to original contract text.
2. **Arithmetic & Relational Invariant Violations**: Raw vision models frequently misread quantities or transcription errors on delivery notes, leading to inventory discrepancies and invalid ERP postings.
3. **Complex Layout Re-ordering**: Contract redlines and amended master agreements feature added, deleted, split, or re-ordered clauses across versions, breaking naive sequential line diffing.

## Decision

1. **Strict Character Span Grounding**:
   - Every extracted contract term or legal clause must maintain exact start/end character offsets (`span_start`, `span_end`) within the source text, cross-referenced with 2D page bounding boxes.
   - Any extracted entity that cannot be deterministically resolved as an exact substring of the original document text layer or OCR output is discarded (`grounded_span is None`).

2. **Deterministic Business Invariant Gates Before ERP / Ontology Ingestion**:
   - Delivery note entities extracted via the fine-tuned Donut model must pass four strict deterministic validation gates:
     * **Arithmetic Invariant**: Sum of extracted line item quantities must exactly equal total quantity ($\sum q_i == Q_{\text{total}}$).
     * **Relational PO Invariant**: Purchase order reference must exist in the Halden P1 ontology.
     * **Supplier Match**: Extracted supplier name must resolve to an approved vendor record.
     * **Date Invariant**: Delivery date must fall within permissible order fulfillment windows.
   - If any validation gate fails or overall extraction confidence drops below calibrated threshold $\tau = 0.90$, the document is routed to the human review queue with high-confidence visual bounding box overlays.

3. **Hybrid OCR & Layout Preprocessing Pipeline**:
   - Magic-byte validation strictly checks initial file signatures (PDF `%PDF-`, PNG, JPEG, TIFF) before disk storage or worker execution; disguised executables are blocked immediately.
   - PyMuPDF native text layer extraction is favored when $> 50$ characters are present. For flat scans, Tesseract OCR (`deu+eng`) generates word-level bounding boxes and confidence scores.
   - Idempotent SQLite/MinIO step tracking (`MAGIC_BYTES`, `PREPROCESS`, `OCR`, `EXTRACTION`, `VALIDATION`) guarantees deterministic worker resumability without duplicate processing.

4. **Hungarian Bipartite Optimal Clause Alignment**:
   - Contract version comparison pairs clauses across versions $V_1$ and $V_2$ using the Hungarian algorithm (`scipy.optimize.linear_sum_assignment`).
   - The cost matrix is constructed using hybrid Jaccard similarity and semantic embedding similarity, correctly handling renumbered, moved, inserted, and deleted clauses.
   - Material legal risk classification (liability cap alterations, shortened termination windows, foreign jurisdiction injection) is evaluated deterministically against `playbooks/halden_v1.yaml`.

## Consequences
- **Positive**: Zero hallucinated legal text in contracts, 100% arithmetic accuracy in delivery note line item ingestion, robust handling of re-ordered legal sections, and sub-millisecond local CPU diffing.
- **Negative**: Scans with severe physical damage or illegible handwriting require human-in-the-loop operator correction in the console UI.
