# 2-Minute Demo Recording Runbook: Project 7 (Tracehub Observability)

## Overview
- **Length**: 2 minutes max
- **Audience**: Hiring Managers / Lead Forward Deployed Engineers / Enterprise IT Architects
- **Core Message**: "Built an on-premises, OpenTelemetry-native LLM observability, eval comparison, online A/B testing, and real-time anomaly alerting platform for Halden Industrie GmbH that runs locally with ClickHouse, tail-sampling, and zero data egress."

---

## Pre-Flight Setup
1. Launch OBS Studio (1920x1080 @ 30fps).
2. Start services: `make up P=observe` and `pnpm --prefix apps/console dev`.
3. Open browser tabs:
   - Tab 1: [http://localhost:3000/observe](http://localhost:3000/observe) (Observe Web Console)
   - Tab 2: [http://localhost:3001](http://localhost:3001) (Grafana Dashboards: admin/admin)
   - Tab 3: [http://localhost:8090/fieldkit-alerts](http://localhost:8090/fieldkit-alerts) (ntfy web push)
   - Tab 4: [http://localhost:8025](http://localhost:8025) (Mailpit SMTP)
4. Terminal window running Git Bash in `D:\mak_dev\FDE`.

---

## Scene-by-Scene Script

### Scene 1: The Problem & Telemetry Pipeline (0:00 - 0:25)
- **Visual**: Show `apps/console/app/observe` overview metrics and throughput charts.
- **Narrative**:
  > "Halden Industrie runs 6 on-premise AI services across manufacturing, RAG, and document extraction. Because of defense supplier contracts, zero telemetry can leave the plant network for Datadog or LangSmith. Tracehub captures every LLM and system span via OpenTelemetry, applies tail sampling—retaining 100% of errors and slow spans—and streams them through Redpanda into ClickHouse at over 100,000 spans per second."

### Scene 2: Hierarchical Span Tree & Trace Waterfall (0:25 - 0:50)
- **Visual**: Click on a slow Assistant trace. The slide-over Gantt waterfall drawer opens.
- **Narrative**:
  > "When an analyst reports a slow response, Tobias doesn't guess. Clicking the trace opens the span waterfall: 24 ms in hybrid BM25 and vector search, 18 ms in cross-encoder reranking, and 1,420 ms in generation. We inspect TTFT, token counts, and full prompt and completion bodies—with regex PII masking and 4KB safety caps enforced at the source."

### Scene 3: Streaming Anomaly Detection & Push Alerts (0:50 - 1:15)
- **Visual**: Switch to terminal, run `uv run python scripts/incident_injector.py`. Switch to ntfy tab and Web Console alert inbox.
- **Narrative**:
  > "Tracehub runs streaming anomaly detection on 1-minute metric rollups using Robust Z-scores on rolling 24-hour median and MAD, EWMA variance bands, and CUSUM control charts. When we inject an anomalous prompt regression, the detector triggers within 2 minutes. The alert deduplicates, respects cooldowns, and instantly pushes to Tobias's phone via self-hosted ntfy and the console inbox."

### Scene 4: Deterministic RCA Attribution with Zero Hallucinations (1:15 - 1:35)
- **Visual**: Click on the alert in the Web Console; open the Root Cause Inspector drawer.
- **Narrative**:
  > "Rather than asking an unconstrained LLM to speculate, our RCA engine computes deterministic, share-weighted contrast contributions across prompt versions, models, routes, and plants. It proves that prompt version 3.0.0-rc caused 87% of the latency delta. Our strict deterministic verifier guarantees that every number in the LLM hypothesis is mathematically grounded in the evidence—zero hallucinations allowed."

### Scene 5: Prompt Registry Diffing, Eval CI & A/B Results (1:35 - 2:00)
- **Visual**: Show the Prompt Registry version diff, Eval Runs comparison with 95% bootstrap CI, and A/B Experiments traffic bars.
- **Narrative**:
  > "Every prompt template in Git is indexed with its SHA-256 hash. The Eval Runs engine aligns candidate and baseline items, computing 95% bootstrap confidence intervals for statistical significance. Our client-side A/B router splits traffic deterministically with automatic safety stop rules. One command, `make eval P=tracehub`, verifies our 20-incident benchmark with 100% recall, 100% precision, and sub-500ms P95 query latency."
