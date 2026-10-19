# 2-Minute Demo Recording Runbook: Project 1 (Mini Foundry)

## Overview
- **Length**: 2 minutes max (120 seconds)
- **Customer**: Halden Industrie GmbH (Operations & Procurement)
- **Core Message**: "Halden had the same supplier formatted 4 different ways across 4 legacy systems with breaking schema drifts and cross-plant visibility issues. Fieldkit ingested 24,000 rows/second, deduplicated with 0.94 F1 record linkage, resolved drifts with LLM suggestions, and enforced native PostgreSQL Row-Level Security with sub-150ms query latency."

---

## Pre-Flight Setup
1. Launch OBS Studio (1920x1080 @ 30fps).
2. Browser tabs prepared (zoom at 110%):
   - Tab 1: [http://localhost:3000/foundry/explorer](http://localhost:3000/foundry/explorer) (Explorer)
   - Tab 2: [http://localhost:3000/foundry/drift](http://localhost:3000/foundry/drift) (Drift Inbox)
   - Tab 3: [http://localhost:3000/foundry/graph](http://localhost:3000/foundry/graph) (Cytoscape Graph)
   - Tab 4: [http://localhost:3000/foundry/review](http://localhost:3000/foundry/review) (ER Review Queue)
   - Tab 5: `evals/reports/foundry/2026-10-19.md` (Master Eval Report)
3. Terminal window open to `D:\mak_dev\FDE`.

---

## Scene-by-Scene Script (2:00)

### Scene 1 (0:00 - 0:20): The Problem -- Messy Enterprise Supplier Data
- **Visual**: Show side-by-side terminal or files displaying:
  1. ERP (Latin-1): `'Mueller Hydr. GmbH & Co KG'` (`V-HAM-882`)
  2. Plant Excel: `'Müller Hydraulik Bauteile GmbH'` (`PLAN-HAM-104`)
  3. Mock SOAP: `'Mueller Hydraulik & Dichtungen e.K.'` (`SOAP-992`)
  4. GLEIF Authoritative: `'Müller Hydraulik AG'` (`LEI: 529900T8BM49AURXP140`)
- **Narrative**:
  > "Halden Industrie had a classic enterprise manufacturing nightmare: the same critical hydraulic cylinder supplier appeared under four conflicting names across Latin-1 ERP exports, planner Excel sheets, a legacy SOAP portal, and official GLEIF filings. Spend analysis and defect tracking were impossible."

### Scene 2 (0:20 - 0:50): One-Command Seed & Drift Governance
- **Visual**: In terminal run `make demo P=foundry`. Switch to browser at `/foundry/drift`.
- **Narrative**:
  > "With a single command `make demo P=foundry`, Fieldkit ingests and lands all sources with SHA-256 deduplication. When a plant planner renamed 'bestelldatum' to 'order_date', our drift engine blocked the breaking schema and used an LLM to propose an automatic column rename. In the Drift Inbox, we approve the mapping with one click."

### Scene 3 (0:50 - 1:15): Explorer, Provenance & Keyset Pagination
- **Visual**: Navigate to `/foundry/explorer`, search `Müller Hydraulik`, click the canonical supplier, hover over properties to show popovers.
- **Narrative**:
  > "Under the hood, Splink 4 Fellegi-Sunter record linkage and our LLM grey-zone adjudicator resolved all four records into one canonical supplier with 0.94 F1 and zero human review. Hovering any attribute displays immutable field-level provenance showing the source system, batch run ID, and survivorship rule applied."

### Scene 4 (1:15 - 1:35): Multi-Hop Ontology Link Graph
- **Visual**: Switch to `/foundry/graph`, click the Supplier node, expand neighbors to Purchase Orders, Shipments, and Quality Incidents at Plant Hamburg (`DE-HAM`).
- **Narrative**:
  > "In the Cytoscape graph canvas, analysts can traverse multi-hop relationships in real time from suppliers to purchase orders, shipments, and quality defect incidents across assembly lines."

### Scene 5 (1:35 - 1:50): Row-Level Security (RLS) Plant Isolation
- **Visual**: Switch user persona in top navbar from **Jana Weber (Admin, Global)** to **Mehmet Yilmaz (Quality, DE-HAM)**. Show Stuttgart (`DE-STR`) rows instantly disappear.
- **Narrative**:
  > "Security is enforced in the PostgreSQL database kernel via Row-Level Security. When logged in as Jana Weber, all plants are visible. When switching to Mehmet Yilmaz at Hamburg, all Stuttgart rows vanish from queries and graph joins with zero application-layer leak risk."

### Scene 6 (1:50 - 2:00): Master Evals & Target Verification
- **Visual**: Display `evals/reports/foundry/2026-10-19.md` summary table.
- **Narrative**:
  > "Every metric is verified via `make eval P=foundry`: ER F1 0.94, 0.0% review queue, 100% drift recall, and sub-135ms API latency under concurrent load. Mini Foundry is production-ready."
