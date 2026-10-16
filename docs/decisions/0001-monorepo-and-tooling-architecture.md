# ADR 0001: Monorepo Architecture and Local-First Tooling

- **Status**: Accepted
- **Date**: 2026-10-16
- **Author**: engrmaziz

## Context
Fieldkit represents an enterprise AI and data platform designed for forward-deployed engineering engagements, simulated for Halden Industrie GmbH. The customer requires on-premise execution, air-gapped security, zero external API key leak risk, and unified governance across 8 flagship AI and data projects.

## Decision
1. **Monorepo Layout**: Use a single monorepo (`packages/*`, `services/*`, `apps/*`, `deploy/`) managed by `uv` (Python 3.12 workspace) and `pnpm`.
2. **Local-First Zero-Dollar AI**: All LLM capabilities execute through a standardized wrapper (`packages/llm`) pointing exclusively to local Ollama endpoints (`qwen2.5:7b`, `nomic-embed-text`). No paid cloud APIs (OpenAI/Anthropic) are permitted in production paths.
3. **Structured Outputs & Deterministic Wrappers**: LLM generations that affect state or trigger actions must pass strict Pydantic schemas and deterministic validation.
4. **Docker Compose Profiles**: To prevent overloading 16 GB developer laptops, use profile-gated Compose services (`core`, `foundry`, `assistant`, `copilot`, `docai`, `vision`, `observe`, `deploy`).

## Consequences
- **Positive**: Clean encapsulation, shared authentication (Keycloak SSO with plant-level RLS), single tracing pipeline, zero cloud bills, offline resilience.
- **Negative**: Model inference speeds depend directly on local host CPU/GPU; initial Docker image pulls require ~25 GB disk.
