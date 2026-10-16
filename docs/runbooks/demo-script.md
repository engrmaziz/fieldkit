# 2-Minute Demo Recording Runbook: Foundation & Shared Stack

## Overview
- **Length**: 2 minutes max
- **Audience**: Hiring managers / Lead Forward Deployed Engineers
- **Core Message**: "Built an air-gapped, zero-dollar enterprise platform foundation for Halden Industrie GmbH with centralized Keycloak SSO, plant-level RLS, deterministic fail-closed LLM validation, and profile-isolated Docker deployment."

## Pre-Flight Setup
1. Launch OBS Studio (1920x1080 @ 30fps).
2. Browser zoom at 125%, bookmarks hidden.
3. Open two tabs:
   - Tab 1: [http://localhost:8000/docs](http://localhost:8000/docs) (Hello service Swagger UI)
   - Tab 2: [http://localhost:8080](http://localhost:8080) (Keycloak Admin Console)
4. Terminal window running Git Bash in `D:\mak_dev\FDE`.

## Scene-by-Scene Script

### Scene 1: The Platform Pitch & Architecture (0:00 - 0:30)
- **Visual**: Show `README.md` and the architecture diagram.
- **Narrative**:
  > "Hi, I'm Haider. This is Fieldkit, an enterprise forward-deployed AI platform built for Halden Industrie, a German hydraulic components manufacturer. We enforce a zero-dollar, card-free constraint where everything runs locally on Docker Compose and Ollama with strict air-gapped security."

### Scene 2: Centralized Identity & Plant-Level RLS (0:30 - 1:00)
- **Visual**: Show Keycloak console and `halden-realm.json`.
- **Narrative**:
  > "Rather than toy passwords, all 8 projects share one Keycloak realm with PKCE for the frontend and bearer tokens for APIs. Users carry plant attributes like Hamburg (`DE-HAM`) and Stuttgart (`DE-STR`). Our common middleware validates tokens against cached JWKS and enforces Row-Level Security so one plant cannot view another plant's defect or production logs unless authorized."

### Scene 3: Deterministic-First LLM Architecture & Fail-Closed Validation (1:00 - 1:30)
- **Visual**: Show `packages/llm/fieldkit_llm/client.py` and `services/hello/fieldkit_hello/main.py`.
- **Narrative**:
  > "All LLM calls funnel through `packages/llm`. We ban unconstrained generation: prompts use versioned Jinja templates, temperature is locked at 0 with fixed seeds, and all machine-consumed outputs pass Pydantic schemas. If a response is malformed, we trigger a single self-correction retry; if that fails, we fail closed with a typed error."

### Scene 4: Live Verification & Automated Evals (1:30 - 2:00)
- **Visual**: Run `make check` and `make eval P=hello` in Git Bash. Show the generated report in `evals/reports/hello/`.
- **Narrative**:
  > "One command `make check` runs our full test suite and type checking across all packages. Running `make eval P=hello` executes reproducible benchmarks against local Ollama models and writes an audited markdown report with latency and schema validity metrics. Everything is deterministic, reproducible, and ready for production."
