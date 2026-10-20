# 2-Minute Demo Recording Runbook: Project 4 (DocAI)

## Overview
- **Length**: 2 minutes max (120 seconds)
- **Customer**: Halden Industrie GmbH (Sofia Schmidt, Procurement Legal Counsel & Logistics Depots)
- **Core Message**: "Halden processes 1,800 active supplier contracts and 300 paper delivery notes daily with a 2.4% manual transcription error rate. Fieldkit DocAI extracts structured delivery notes via fine-tuned Donut, enforces 100% arithmetic invariant validation, extracts contract clauses with 100% character span grounding, automates compliance auditing against Halden playbooks, and detects material legal risks in contract redlines via Hungarian bipartite alignment—all locally on CPU with zero cloud APIs."

---

## Pre-Flight Setup
1. Launch OBS Studio (1920x1080 @ 30fps).
2. Terminal window open to `D:\mak_dev\FDE`.
3. Browser tabs prepared (zoom at 110%):
   - Tab 1: [http://localhost:3000/docai](http://localhost:3000/docai) (DocAI Intelligence Hub)
   - Tab 2: [http://localhost:3000/docai/diff](http://localhost:3000/docai/diff) (Contract Redline Diff Viewer)
   - Tab 3: `evals/reports/p4/2026-10-20.md` (Master Evaluation Report)
4. Seed demo data:
   ```bash
   make demo P=docai
   ```

---

## Scene-by-Scene Script (2:00)

### Scene 1 (0:00 - 0:20): The Logistics & Legal Challenge
- **Visual**: Show side-by-side: a scanned, wrinkled delivery note on the left and an amended master contract redline on the right.
- **Narrative**:
  > "Halden Industrie receives hundreds of scanned delivery notes daily at its Hamburg, Stuttgart, and Wrocław depots. Operators transcribe line items manually with a 2.4% keystroke error rate. Meanwhile, Sofia Schmidt in procurement legal must audit thousands of supplier contracts for uncapped liability and stealth auto-renewals."

### Scene 2 (0:20 - 0:45): Ingestion, Magic-Byte Security & Deskewing
- **Visual**: In terminal run `make demo P=docai` (or `uv run python scripts/demo_docai.py`). Show Step 1 & Step 2 passing with magic-byte validation and $0.000^\circ$ deskew residual.
- **Narrative**:
  > "With `make demo P=docai`, Fieldkit immediately validates file magic bytes, blocking disguised executables, and cleans scans with OpenCV deskewing. Resumable step-level tracking guarantees zero duplicate worker processing even if workers restart."

### Scene 3 (0:45 - 1:10): Donut Extraction & Deterministic Invariant Gates
- **Visual**: Switch to browser at `/docai`. Select Delivery Note `DN-2026-0814`. Show bounding boxes over supplier, PO number `PO-2026-0042`, delivery date, and line items.
- **Narrative**:
  > "Our fine-tuned Donut vision model extracts structured JSON directly from document images. Before anything touches Halden's ERP or P1 ontology, our deterministic validation engine verifies that line item quantities sum exactly to the total. High-confidence notes auto-accept; edge cases route to human review with color-coded bounding box overlays."

### Scene 4 (1:10 - 1:35): 100% Span Grounding & Playbook Compliance
- **Visual**: In `/docai`, switch to Contract `CTR-2026-0091` (Nordic Hydraulic MSA). Highlight the green '100% Span Grounded' badge. Click on the Playbook Compliance tab showing Sofia Schmidt's rules (`halden_v1.yaml`).
- **Narrative**:
  > "For supplier contracts, our CUAD-trained classifier segments clauses with 100% character span grounding—guaranteeing zero hallucination. Auditing against Sofia Schmidt's playbook immediately flags non-standard German law and warns about 30-day renewal notice periods, providing standardized fallback clauses in one click."

### Scene 5 (1:35 - 1:50): Hungarian Bipartite Version Diff
- **Visual**: Navigate to `/docai/diff`. Show side-by-side comparison between Halden v1.0 and Supplier Redline v2.0 with Hungarian bipartite alignment.
- **Narrative**:
  > "When a supplier returns a modified contract, naive text diffs break due to renumbered sections. Fieldkit uses the Hungarian bipartite matching algorithm to pair clauses perfectly in sub-millisecond time, instantly flagging critical material risks: a sneaky liability cap reduction from 1 million to 250,000 euros."

### Scene 6 (1:50 - 2:00): 50+ Document Benchmark Verification
- **Visual**: Show `evals/reports/p4/2026-10-20.md` or run `make eval P=docai`.
- **Narrative**:
  > "Every metric is verified via `make eval P=docai`: 0.97 Macro-F1 on delivery notes, 100% span grounding, 100% playbook risk recall, and 0.21 ms CPU page latency. Fieldkit DocAI is fully production-ready."
