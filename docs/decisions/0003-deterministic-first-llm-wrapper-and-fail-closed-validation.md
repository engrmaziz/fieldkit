# ADR 0003: Deterministic-First LLM Architecture and Fail-Closed Validation

- **Status**: Accepted
- **Date**: 2026-10-16
- **Author**: engrmaziz

## Context
In forward-deployed engineering engagements, probabilistic models must never directly mutate relational databases, trigger ERP transactions, or bypass enterprise compliance rules without deterministic validation. Unconstrained free-form generation leads to silent schema corruption, hallucinatory SQL queries, and irreproducible operational workflows.

## Decision
1. **Single LLM Client Gateway (`packages/llm`)**:
   - Every service must interact with local Ollama instances strictly through the `packages/llm` client. Direct HTTP calls to LLM endpoints are prohibited.
   - Mandatory invocation parameters: `task` name, `model`, `prompt_version`, and `timeout` (default 60s local).
   - Distributed OpenTelemetry (OTel) span emission per call capturing token counts, latency, temperature, seed, and cache hit state for Project 7 observability.
2. **Strict Structured Output & Fail-Closed Validation**:
   - Any machine-consumed LLM generation must supply a Pydantic schema passed directly to Ollama's `format` parameter.
   - In the event of schema validation failure, the client performs exactly one self-correction retry with the Pydantic error details appended to the prompt.
   - If the retry fails validation, the client raises `LLMValidationError` and **fails closed**. Under no circumstance will malformed or partial output be passed to caller business logic.
3. **Deterministic Defaults**:
   - `temperature = 0.0` for all extraction, SQL generation, and classification tasks.
   - Fixed `seed` parameter support for reproducible offline evaluations.
4. **Jinja2 Prompt Template Versioning**:
   - Prompts must reside in `.jinja` files under `packages/*/prompts/` (or `services/*/prompts/`).
   - Every template must declare a version header (`{# version: X.Y.Z #}`). Missing headers trigger a compile-time/load-time `PromptVersionError`.
5. **Disk Caching Strategy**:
   - SHA-256 disk cache is active during development and evaluation runs for instant replay and regression testing.
   - Disk caching is explicitly bypassed when `is_chat=True` for real-time conversational interfaces.

## Consequences
- **Positive**: Complete reproducibility, guaranteed zero schema corruption, full observability across all model calls, and transparent prompt version tracking.
- **Negative**: Increased latency during self-correction retries when initial responses fail validation.
