# Fieldkit — agent rules

## Product
Fieldkit is a forward-deployed AI platform: data fusion (P1), RAG + NL2SQL (P2),
ops copilot (P3), document AI (P4), video analytics (P5), defect inspection (P6),
LLM observability (P7), air-gapped deploy + workflow engine (P8).
Everything runs locally. No paid APIs, no cloud services. LLMs via Ollama only.

## Stack
- Python 3.12, uv workspaces, FastAPI, Pydantic v2, SQLAlchemy 2 (async), Alembic
- Postgres 16 + pgvector, DuckDB, ClickHouse, Redis, Redpanda
- Frontend: Next.js (App Router) + TypeScript + Tailwind + shadcn/ui, pnpm
- Go 1.23+ for services/workflow-engine
- Docker Compose for local; Helm on k3d for P8

## Conventions
- Monorepo layout: services/<name>, packages/<name>, apps/<name>, deploy/, evals/, data/ (gitignored)
- Every service: /healthz, /readyz, structured JSON logs, OpenTelemetry traces, settings via env (pydantic-settings)
- Type hints everywhere; ruff + mypy --strict on packages/; tests with pytest, >=80% on core logic
- LLM calls ONLY through packages/llm (one client, retries, timeouts, structured output, tracing, caching)
- LLM output that affects data or actions MUST pass a Pydantic schema + deterministic validator
- No new dependency without stating why in the PR description
- Never hardcode secrets, never commit data/ or models/

## How to work
1. Before coding, restate the task and list files you will touch. Ask if ambiguous.
2. Work in small slices; run `make check` (lint+type+test) after each slice.
3. Write tests first for parsers, validators, and state machines.
4. Do not modify unrelated files. Do not delete tests to make them pass.
5. End with: what changed, how to run it, known limitations.
