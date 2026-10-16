> From: https://claude.ai/chat/5aefb46b-178e-4153-98fb-c98fde5db2f2

# you asked

message time: 2026-10-16 01:48:19

give a list of 10 most complex projects that we can build and get a role of Forward Deployed Engineer. must be locally run-able and must be 0$. any stack.

---

# claude response

Here are 10 projects, picked for what FDE hiring managers look for: messy data, real integrations, deployment, and measurable outcomes. All run locally on free tools (Ollama, Postgres, DuckDB, Docker).

1. **Mini Palantir Foundry (ontology + data fusion)**: Ingest CSVs, APIs, and PDFs into a unified object graph with lineage, permissions, and a query UI. *Stack: Postgres, DuckDB, FastAPI, React, Ollama.*

2. **Enterprise RAG with evals and access control**: Hybrid search (BM25 + vectors), per-user document permissions, citation checking, and an automated eval harness. *Stack: pgvector, Ollama, Python, Ragas-style custom evals.*

3. **Multi-agent ops copilot with human-in-the-loop**: Agents that triage tickets, query a database, draft actions, and escalate for approval, with full audit trails. *Stack: LangGraph or custom, Ollama, SQLite, Next.js.*

4. **Legacy system integration engine**: Connectors that scrape and normalize data from "ugly" sources (old SOAP APIs, Excel dumps, email attachments) into a clean API with schema drift detection. *Stack: Go or Python, Playwright, Airflow-lite.*

5. **Document intelligence pipeline (invoices/contracts)**: OCR, layout parsing, field extraction, validation rules, and a review UI with confidence scoring. *Stack: Tesseract, local VLM via Ollama, Postgres.*

6. **Real-time anomaly detection and alerting platform**: Streaming ingestion, drift detection, root-cause suggestions from an LLM, and Slack-style notifications. *Stack: Redpanda or Kafka in Docker, ClickHouse, Python.*

7. **LLM observability and eval platform**: Trace capture, prompt versioning, regression tests, cost and latency dashboards, and A/B comparisons (a local Langfuse-style tool). *Stack: OpenTelemetry, ClickHouse, SvelteKit.*

8. **Natural-language-to-SQL analytics assistant**: Schema-aware query generation, SQL validation and sandboxing, row-level security, and self-correction on errors. *Stack: DuckDB, Ollama, sqlglot, Streamlit.*

9. **On-prem deployment kit**: One-command, air-gapped install (Docker Compose, Helm on k3s) with config management, health checks, backups, and a runbook. Pairs well with any project above. *Stack: k3s, Helm, Terraform-local, Prometheus, Grafana.*

10. **Workflow automation engine (Temporal/n8n-style)**: Durable workflows with retries, state, a visual builder, and LLM-powered steps. *Stack: Rust or Go core, SQLite, React Flow.*

**What makes these land an FDE role:**
- Frame each as a customer case study: fictional client, messy data, problem, deployment, measured result.
- Include a 2-minute demo video and a README with architecture, trade-offs, and failure modes.
- Use realistic messy datasets (public ones like Enron emails, SEC filings, NYC open data), not clean toy data.
- Projects 1, 2, 4, and 9 combined into one end-to-end story are the strongest signal.

I can turn any of these into a detailed build plan with milestones if you tell me which ones.

---

# you asked

message time: 2026-10-16 01:50:08

add 2-3 cv related projects too

---

# claude response

Here are 3 computer vision projects in the same FDE style: real-world deployment, messy inputs, runs fully local on free tools.

11. **Industrial defect inspection system (edge-deployable)**: Detect surface defects on parts (cracks, scratches, misalignment) using public datasets like MVTec AD or NEU steel defects. Include anomaly detection for unseen defect types, a labeling and retraining loop, confidence thresholds with a human review queue, and an ONNX-exported model running on CPU. *Stack: PyTorch, Anomalib, ONNX Runtime, FastAPI, React.*

12. **Multi-camera video analytics platform**: Ingest RTSP or recorded video streams, run detection and tracking (people, vehicles, PPE compliance), and define zone rules like "alert if someone enters this area without a helmet." Add re-identification across cameras, event search ("show all forklift near-misses today"), and per-camera health monitoring. *Stack: YOLO (Ultralytics), ByteTrack, GStreamer or FFmpeg, Redis, ClickHouse, Next.js.*

13. **Document and ID vision pipeline with a custom-trained model**: Fine-tune a layout and field detector for forms, receipts, or ID-style documents. Include synthetic data generation for training, handling of skewed and low-quality scans, a VLM fallback via Ollama for hard cases, and an accuracy dashboard by document type. This overlaps with project 5 but goes deeper on the vision side (training, augmentation, error analysis). *Stack: PyTorch, Albumentations, LayoutLM or Donut, Tesseract, Ollama.*

**How these strengthen your story:**
- FDEs at CV-heavy companies (Anduril, Palantir, defense and manufacturing startups) value the "model works in the lab, now make it work on a customer's bad cameras" angle. Document lighting changes, compression artifacts, and drift as explicit failure modes.
- Project 12 pairs well with 6 (anomaly alerting) and 9 (on-prem deployment kit) for a full "ship vision to a factory floor" narrative.
- Report real metrics: precision/recall per defect class, FPS on CPU, latency, and false alarm rate per hour.

If you want, I can rank all 13 by how strongly they signal FDE readiness and suggest a 3-project portfolio to build first.

---

# you asked

message time: 2026-10-16 01:50:54

add 2-3 nlp fde related projects

---

# claude response

Here are 3 NLP projects in the same style: messy real-world text, local-only, free tools.

14. **Multilingual customer support intelligence platform**: Ingest support tickets, emails, and chat logs in English and German (fits DACH clients). Do intent classification, entity extraction, sentiment, auto-routing, and duplicate/cluster detection to surface the top emerging issues each week. Include a fine-tuned small classifier (not just prompting) with a comparison against LLM zero-shot on accuracy, cost, and latency. *Stack: Hugging Face Transformers (XLM-R or German BERT), spaCy, BERTopic, Ollama, Postgres, FastAPI.*

15. **Contract and compliance analysis engine**: Parse long legal or policy documents (public datasets: CUAD contracts, SEC filings, GDPR texts). Extract clauses, flag risky or missing terms against a configurable playbook, and compare versions with redline-style diffs. Add cross-document Q&A with clause-level citations and a reviewer UI where corrections feed back into evaluation sets. *Stack: Python, Ollama, pgvector, sentence-transformers, Unstructured or PyMuPDF, React.*

16. **Domain-adapted entity resolution and knowledge extraction pipeline**: Take messy records (company names, addresses, product descriptions from multiple sources) and resolve them into canonical entities. Combine fuzzy matching, embedding similarity, and an LLM adjudicator for borderline cases, and extract relations into a knowledge graph. Show precision/recall against a labeled gold set and a human-in-the-loop merge/split UI. *Stack: Splink or dedupe, sentence-transformers, Neo4j Community or Postgres, Ollama, Streamlit.*

**Why these work for FDE:**
- Project 14 is the most realistic customer story: a client drowning in tickets, with measurable results like routing accuracy and hours saved.
- Project 15 shows you can handle long, high-stakes documents with traceable citations, which enterprise and legal-tech clients care about.
- Project 16 is quiet but valuable: entity resolution is one of the most common real FDE tasks, and few portfolios have it.
- Evaluate honestly in all three: labeled test sets, error analysis, and where the model fails. That is what separates these from demo-ware.

Projects 2 (RAG), 8 (NL-to-SQL), and 15 share infrastructure, so you can build them on one common platform and present them as a single product.

---

# you asked

message time: 2026-10-16 01:52:39

now give a complete list. give 8 big, complex, tough (but 0$) projects that can maximize my chances for forward deployed engineer

---

# claude response

Here are 8 flagship projects, consolidated from all 16 earlier ones. Each is hard, free, and runs locally.

1. **Mini Foundry: data fusion and ontology platform** *(merges 1, 4, 16)*
   Ingest messy CSVs, legacy APIs, Excel dumps, and PDFs. Resolve entities, build an object graph with lineage and permissions, and detect schema drift.
   *Stack: Postgres, DuckDB, FastAPI, React, Splink, Ollama.*

2. **Enterprise RAG and NL-to-SQL assistant with evals** *(merges 2, 8)*
   Hybrid search, per-user access control, citation checking, schema-aware SQL generation with sandboxing, and an automated eval harness.
   *Stack: pgvector, sqlglot, Ollama, Python.*

3. **Multi-agent ops copilot with human-in-the-loop** *(merges 3, 14)*
   Triages English and German tickets, queries databases, drafts actions, escalates for approval, and keeps a full audit trail. Includes a fine-tuned classifier compared against LLM zero-shot on accuracy, cost, and latency.
   *Stack: LangGraph or custom, XLM-R, BERTopic, SQLite, Next.js.*

4. **Contract and document intelligence engine** *(merges 5, 13, 15)*
   OCR and layout parsing, clause extraction, risk flags against a playbook, version diffs, and a review UI where corrections feed the eval set. Add a custom-trained field detector with a VLM fallback.
   *Stack: Donut or LayoutLM, Tesseract, PyMuPDF, Ollama, React.*

5. **Multi-camera video analytics platform** *(project 12)*
   Detection, tracking, and zone rules (for example, PPE violations), plus cross-camera re-ID, event search, and camera health monitoring.
   *Stack: Ultralytics YOLO, ByteTrack, FFmpeg, Redis, ClickHouse.*

6. **Industrial defect inspection with a retraining loop** *(project 11)*
   Anomaly detection for unseen defects, a human review queue, ONNX CPU deployment, and per-class precision and recall.
   *Stack: Anomalib, PyTorch, ONNX Runtime, FastAPI.*

7. **LLM observability, eval, and anomaly alerting platform** *(merges 6, 7)*
   Trace capture, prompt versioning, regression tests, cost and latency dashboards, and streaming drift and anomaly alerts with LLM root-cause hints.
   *Stack: OpenTelemetry, Redpanda, ClickHouse, SvelteKit.*

8. **Air-gapped deployment kit and durable workflow engine** *(merges 9, 10)*
   A one-command on-prem install with health checks, backups, and a runbook, plus a workflow engine with retries, durable state, and LLM steps.
   *Stack: k3s, Helm, Prometheus, Grafana, Go or Rust, SQLite.*

**Build order for maximum FDE signal:**
- **First:** 1, 2, and 8, deployed together as one platform. This is the core "walk into a customer and ship" story.
- **Then:** 3 or 4 for the LLM and document angle.
- **Finally:** 5 or 6 if you're targeting CV-heavy companies (Anduril, Palantir, manufacturing and defense startups).

**For each project, ship:**
- A fictional customer case study with a messy-data problem and a measured result.
- A 2-minute demo video.
- A README with architecture, trade-offs, and failure modes.
- Real metrics: accuracy, latency, cost, and false alarm rate.

I can turn any of these into a milestone-by-milestone build plan if you tell me which to start with.