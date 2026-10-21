export type StepType = "http" | "wait" | "branch" | "map" | "human_approval";

export interface RetryPolicyUI {
  max_attempts: number;
  initial_interval_sec?: number;
  backoff_multiplier?: number;
}

export interface WorkflowStepUI {
  id: string;
  type: StepType;
  depends_on?: string[];
  url?: string;
  method?: "GET" | "POST" | "PUT" | "DELETE";
  headers?: Record<string, string>;
  timeout_sec?: number;
  retry_policy?: RetryPolicyUI;
  compensate_with?: string;
  duration?: string;
  condition?: string;
  then_step?: string;
  else_step?: string;
  items_path?: string;
  concurrency?: number;
  step_template?: Partial<WorkflowStepUI>;
  signal_name?: string;
  required_role?: string;
  description?: string;
}

export interface WorkflowDefinitionUI {
  name: string;
  version: string;
  description: string;
  schedule?: string;
  steps: WorkflowStepUI[];
  compensations?: WorkflowStepUI[];
  rawYaml?: string;
}

export type RunStatus = "pending" | "running" | "completed" | "failed" | "suspended" | "cancelled";
export type StepStatus = "pending" | "running" | "completed" | "failed" | "skipped" | "compensating" | "compensated";

export interface WorkflowEventUI {
  id: string;
  run_id: string;
  sequence_num: number;
  event_type: string;
  step_id?: string;
  timestamp: string;
  payload?: Record<string, unknown>;
}

export interface WorkflowRunUI {
  id: string;
  workflow_name: string;
  workflow_version: string;
  status: RunStatus;
  started_at: string;
  finished_at?: string;
  duration_ms?: number;
  step_states: Record<string, StepStatus>;
  suspended_at_step?: string;
  required_signal?: string;
  events: WorkflowEventUI[];
}

export const SHIPPED_WORKFLOWS: WorkflowDefinitionUI[] = [
  {
    name: "retrain-promote",
    version: "1.0.0",
    description: "Project 6: Continuous defect retraining, frozen evaluation gate, shadow inference, and Quality Lead human promotion with rollback saga",
    schedule: "0 3 * * 0",
    steps: [
      {
        id: "trigger_retraining",
        type: "http",
        url: "http://localhost:8005/inspect/retrain",
        method: "POST",
        timeout_sec: 120,
        compensate_with: "clean_candidate_artifacts",
        description: "Trigger LoRA fine-tuning on new operator defect adjudication queue",
      },
      {
        id: "evaluate_frozen_gate",
        type: "http",
        depends_on: ["trigger_retraining"],
        url: "http://localhost:8005/inspect/shadow/report",
        method: "GET",
        timeout_sec: 30,
        description: "Execute frozen test set evaluation, checking Accuracy >= 94.0% gate",
      },
      {
        id: "await_lead_approval",
        type: "human_approval",
        depends_on: ["evaluate_frozen_gate"],
        signal_name: "promote_approved",
        required_role: "Quality Lead (M. Yilmaz)",
        timeout_sec: 86400,
        description: "Human-in-the-loop gate requiring explicit sign-off before production release",
      },
      {
        id: "promote_to_production",
        type: "http",
        depends_on: ["await_lead_approval"],
        url: "http://localhost:8005/inspect/models/promote",
        method: "POST",
        compensate_with: "rollback_model",
        description: "Atomically promote shadow candidate to active inspection line model",
      },
    ],
    compensations: [
      {
        id: "rollback_model",
        type: "http",
        url: "http://localhost:8005/inspect/models/rollback",
        method: "POST",
        description: "Saga compensation: Revert production pointer to previous blessed baseline",
      },
      {
        id: "clean_candidate_artifacts",
        type: "http",
        url: "http://localhost:8005/inspect/models/cleanup",
        method: "POST",
        description: "Saga compensation: Prune stale checkpoint tensors from MinIO staging",
      },
    ],
    rawYaml: `name: retrain-promote
version: 1.0.0
description: "Project 6: Automated defect retraining, frozen evaluation gate, shadow inference, and Quality Lead promotion"
schedule: "0 3 * * 0"
steps:
  - id: trigger_retraining
    type: http
    url: "http://localhost:8005/inspect/retrain"
    method: "POST"
    compensate_with: "clean_candidate_artifacts"
    timeout_sec: 120

  - id: evaluate_frozen_gate
    type: http
    depends_on: ["trigger_retraining"]
    url: "http://localhost:8005/inspect/shadow/report"
    method: "GET"

  - id: await_lead_approval
    type: human_approval
    depends_on: ["evaluate_frozen_gate"]
    signal_name: "promote_approved"

  - id: promote_to_production
    type: http
    depends_on: ["await_lead_approval"]
    url: "http://localhost:8005/inspect/models/promote"
    method: "POST"
    compensate_with: "rollback_model"

compensations:
  - id: rollback_model
    type: http
    url: "http://localhost:8005/inspect/models/rollback"
    method: "POST"

  - id: clean_candidate_artifacts
    type: http
    url: "http://localhost:8005/inspect/models/cleanup"
    method: "POST"
`,
  },
  {
    name: "nightly-ingest",
    version: "1.0.0",
    description: "Project 1: Halden Industrie nightly multi-source data ingestion, schema drift profiling, and entity resolution",
    schedule: "0 2 * * *",
    steps: [
      {
        id: "ingest_erp",
        type: "http",
        url: "http://localhost:8001/ingest/erp",
        method: "POST",
        timeout_sec: 60,
        retry_policy: {
          max_attempts: 3,
          initial_interval_sec: 2,
          backoff_multiplier: 2.0,
        },
        description: "SAP ERP connector pulling daily inventory & work order delta records",
      },
      {
        id: "ingest_soap",
        type: "http",
        url: "http://localhost:8001/ingest/soap",
        method: "POST",
        timeout_sec: 60,
        description: "Legacy SOAP plant telemetry connector extracting machine state metrics",
      },
      {
        id: "profile_drift",
        type: "http",
        depends_on: ["ingest_erp", "ingest_soap"],
        url: "http://localhost:8001/drift/profile",
        method: "POST",
        description: "Calculate Kolmogorov-Smirnov drift metrics against baseline schema",
      },
      {
        id: "resolve_entities",
        type: "http",
        depends_on: ["profile_drift"],
        url: "http://localhost:8001/er/resolve",
        method: "POST",
        description: "Splink probabilistic linking + LLM entity disambiguation",
      },
      {
        id: "promote_staging",
        type: "http",
        depends_on: ["resolve_entities"],
        url: "http://localhost:8001/staging/promote",
        method: "POST",
        description: "Promote deduplicated canonical records into DuckDB & ClickHouse gold tier",
      },
    ],
    rawYaml: `name: nightly-ingest
version: 1.0.0
description: "Project 1: Halden Industrie nightly multi-source data ingestion, schema drift profiling, and entity resolution"
schedule: "0 2 * * *"
steps:
  - id: ingest_erp
    type: http
    url: "http://localhost:8001/ingest/erp"
    method: "POST"
    timeout_sec: 60
    retry_policy:
      max_attempts: 3
      initial_interval_sec: 2
      backoff_multiplier: 2.0

  - id: ingest_soap
    type: http
    url: "http://localhost:8001/ingest/soap"
    method: "POST"
    timeout_sec: 60

  - id: profile_drift
    type: http
    depends_on: ["ingest_erp", "ingest_soap"]
    url: "http://localhost:8001/drift/profile"
    method: "POST"

  - id: resolve_entities
    type: http
    depends_on: ["profile_drift"]
    url: "http://localhost:8001/er/resolve"
    method: "POST"

  - id: promote_staging
    type: http
    depends_on: ["resolve_entities"]
    url: "http://localhost:8001/staging/promote"
    method: "POST"
`,
  },
  {
    name: "daily-backup",
    version: "1.0.0",
    description: "Project 8: Automated point-in-time PostgreSQL snapshot and MinIO object storage mirror",
    schedule: "0 4 * * *",
    steps: [
      {
        id: "snapshot_postgres",
        type: "http",
        url: "http://localhost:8008/backup/postgres",
        method: "POST",
        description: "Stream pg_dump binary archive with schema and vector embeddings",
      },
      {
        id: "mirror_minio",
        type: "http",
        url: "http://localhost:8008/backup/minio",
        method: "POST",
        description: "Archive landing, docai, inspection, and staging S3 buckets",
      },
      {
        id: "verify_checksums",
        type: "http",
        depends_on: ["snapshot_postgres", "mirror_minio"],
        url: "http://localhost:8008/backup/verify",
        method: "POST",
        description: "Compute SHA-256 digests and write verified disaster recovery manifest",
      },
    ],
    rawYaml: `name: daily-backup
version: 1.0.0
description: "Project 8: Automated point-in-time PostgreSQL snapshot and MinIO object storage mirror"
schedule: "0 4 * * *"
steps:
  - id: snapshot_postgres
    type: http
    url: "http://localhost:8008/backup/postgres"
    method: "POST"

  - id: mirror_minio
    type: http
    url: "http://localhost:8008/backup/minio"
    method: "POST"

  - id: verify_checksums
    type: http
    depends_on: ["snapshot_postgres", "mirror_minio"]
    url: "http://localhost:8008/backup/verify"
    method: "POST"
`,
  },
  {
    name: "weekly-insights",
    version: "1.0.0",
    description: "Project 3: Plant scrap correlation analysis and executive management copilot briefing",
    schedule: "0 6 * * 1",
    steps: [
      {
        id: "fetch_scrap_metrics",
        type: "http",
        url: "http://localhost:8003/api/copilot/scrap-metrics",
        method: "GET",
        description: "Pull 7-day scrap rates by shift, machine station, and steel grade",
      },
      {
        id: "synthesize_briefing",
        type: "http",
        depends_on: ["fetch_scrap_metrics"],
        url: "http://localhost:8003/api/copilot/synthesize",
        method: "POST",
        description: "Ollama LLM root cause analysis of casting mold temperature anomalies",
      },
      {
        id: "dispatch_executive_email",
        type: "http",
        depends_on: ["synthesize_briefing"],
        url: "http://localhost:8003/api/copilot/dispatch",
        method: "POST",
        description: "Send formatted briefing to Operations Director & Plant Supervisors",
      },
    ],
    rawYaml: `name: weekly-insights
version: 1.0.0
description: "Project 3: Plant scrap correlation analysis and executive management copilot briefing"
schedule: "0 6 * * 1"
steps:
  - id: fetch_scrap_metrics
    type: http
    url: "http://localhost:8003/api/copilot/scrap-metrics"
    method: "GET"

  - id: synthesize_briefing
    type: http
    depends_on: ["fetch_scrap_metrics"]
    url: "http://localhost:8003/api/copilot/synthesize"
    method: "POST"

  - id: dispatch_executive_email
    type: http
    depends_on: ["synthesize_briefing"]
    url: "http://localhost:8003/api/copilot/dispatch"
    method: "POST"
`,
  },
  {
    name: "nightly-evals",
    version: "1.0.0",
    description: "Project 2 & 7: Automated RAG/NL2SQL golden benchmark and LLM latency regression test",
    schedule: "0 1 * * *",
    steps: [
      {
        id: "run_rag_eval",
        type: "http",
        url: "http://localhost:8002/api/eval/rag",
        method: "POST",
        description: "Run 50 golden queries against pgvector knowledge index",
      },
      {
        id: "run_nl2sql_eval",
        type: "http",
        url: "http://localhost:8002/api/eval/nl2sql",
        method: "POST",
        description: "Execute 50 golden NL2SQL prompts against DuckDB analytical schema",
      },
      {
        id: "check_quality_gates",
        type: "http",
        depends_on: ["run_rag_eval", "run_nl2sql_eval"],
        url: "http://localhost:8006/api/gates/check",
        method: "POST",
        description: "Assert RAG Faithfulness >= 0.85 and NL2SQL Executability >= 0.90",
      },
      {
        id: "publish_eval_report",
        type: "http",
        depends_on: ["check_quality_gates"],
        url: "http://localhost:8006/api/reports/publish",
        method: "POST",
        description: "Write timestamped evaluation markdown report and update badges",
      },
    ],
    rawYaml: `name: nightly-evals
version: 1.0.0
description: "Project 2 & 7: Automated RAG/NL2SQL golden benchmark and LLM latency regression test"
schedule: "0 1 * * *"
steps:
  - id: run_rag_eval
    type: http
    url: "http://localhost:8002/api/eval/rag"
    method: "POST"

  - id: run_nl2sql_eval
    type: http
    url: "http://localhost:8002/api/eval/nl2sql"
    method: "POST"

  - id: check_quality_gates
    type: http
    depends_on: ["run_rag_eval", "run_nl2sql_eval"]
    url: "http://localhost:8006/api/gates/check"
    method: "POST"

  - id: publish_eval_report
    type: http
    depends_on: ["check_quality_gates"]
    url: "http://localhost:8006/api/reports/publish"
    method: "POST"
`,
  },
];

export const MOCK_RUNS: WorkflowRunUI[] = [
  {
    id: "run-7c33-4a12",
    workflow_name: "retrain-promote",
    workflow_version: "1.0.0",
    status: "suspended",
    started_at: "2026-10-21T23:15:00Z",
    suspended_at_step: "await_lead_approval",
    required_signal: "promote_approved",
    step_states: {
      trigger_retraining: "completed",
      evaluate_frozen_gate: "completed",
      await_lead_approval: "running",
      promote_to_production: "pending",
    },
    events: [
      {
        id: "evt-01",
        run_id: "run-7c33-4a12",
        sequence_num: 1,
        event_type: "run_started",
        timestamp: "2026-10-21T23:15:00Z",
      },
      {
        id: "evt-02",
        run_id: "run-7c33-4a12",
        sequence_num: 2,
        event_type: "step_started",
        step_id: "trigger_retraining",
        timestamp: "2026-10-21T23:15:01Z",
      },
      {
        id: "evt-03",
        run_id: "run-7c33-4a12",
        sequence_num: 3,
        event_type: "step_completed",
        step_id: "trigger_retraining",
        timestamp: "2026-10-21T23:17:15Z",
        payload: { loss: 0.082, epochs: 5, candidate_id: "cand-20261021-lora" },
      },
      {
        id: "evt-04",
        run_id: "run-7c33-4a12",
        sequence_num: 4,
        event_type: "step_started",
        step_id: "evaluate_frozen_gate",
        timestamp: "2026-10-21T23:17:16Z",
      },
      {
        id: "evt-05",
        run_id: "run-7c33-4a12",
        sequence_num: 5,
        event_type: "step_completed",
        step_id: "evaluate_frozen_gate",
        timestamp: "2026-10-21T23:17:42Z",
        payload: { accuracy: 0.948, mAP: 0.884, gate_status: "PASSED" },
      },
      {
        id: "evt-06",
        run_id: "run-7c33-4a12",
        sequence_num: 6,
        event_type: "step_started",
        step_id: "await_lead_approval",
        timestamp: "2026-10-21T23:17:43Z",
      },
      {
        id: "evt-07",
        run_id: "run-7c33-4a12",
        sequence_num: 7,
        event_type: "run_suspended",
        timestamp: "2026-10-21T23:17:43Z",
        payload: { signal_name: "promote_approved", gate: "Quality Lead Approval" },
      },
    ],
  },
  {
    id: "run-92cb-ae9d",
    workflow_name: "nightly-ingest",
    workflow_version: "1.0.0",
    status: "completed",
    started_at: "2026-10-21T02:00:00Z",
    finished_at: "2026-10-21T02:04:12Z",
    duration_ms: 252000,
    step_states: {
      ingest_erp: "completed",
      ingest_soap: "completed",
      profile_drift: "completed",
      resolve_entities: "completed",
      promote_staging: "completed",
    },
    events: [
      { id: "evt-11", run_id: "run-92cb-ae9d", sequence_num: 1, event_type: "run_started", timestamp: "2026-10-21T02:00:00Z" },
      { id: "evt-12", run_id: "run-92cb-ae9d", sequence_num: 2, event_type: "step_completed", step_id: "ingest_erp", timestamp: "2026-10-21T02:01:10Z" },
      { id: "evt-13", run_id: "run-92cb-ae9d", sequence_num: 3, event_type: "step_completed", step_id: "ingest_soap", timestamp: "2026-10-21T02:01:25Z" },
      { id: "evt-14", run_id: "run-92cb-ae9d", sequence_num: 4, event_type: "step_completed", step_id: "profile_drift", timestamp: "2026-10-21T02:02:18Z" },
      { id: "evt-15", run_id: "run-92cb-ae9d", sequence_num: 5, event_type: "step_completed", step_id: "resolve_entities", timestamp: "2026-10-21T02:03:40Z" },
      { id: "evt-16", run_id: "run-92cb-ae9d", sequence_num: 6, event_type: "step_completed", step_id: "promote_staging", timestamp: "2026-10-21T02:04:12Z" },
      { id: "evt-17", run_id: "run-92cb-ae9d", sequence_num: 7, event_type: "run_completed", timestamp: "2026-10-21T02:04:12Z" },
    ],
  },
  {
    id: "run-a76d-8eab",
    workflow_name: "daily-backup",
    workflow_version: "1.0.0",
    status: "completed",
    started_at: "2026-10-21T04:00:00Z",
    finished_at: "2026-10-21T04:01:48Z",
    duration_ms: 108000,
    step_states: {
      snapshot_postgres: "completed",
      mirror_minio: "completed",
      verify_checksums: "completed",
    },
    events: [
      { id: "evt-21", run_id: "run-a76d-8eab", sequence_num: 1, event_type: "run_started", timestamp: "2026-10-21T04:00:00Z" },
      { id: "evt-22", run_id: "run-a76d-8eab", sequence_num: 2, event_type: "step_completed", step_id: "snapshot_postgres", timestamp: "2026-10-21T04:00:52Z" },
      { id: "evt-23", run_id: "run-a76d-8eab", sequence_num: 3, event_type: "step_completed", step_id: "mirror_minio", timestamp: "2026-10-21T04:01:20Z" },
      { id: "evt-24", run_id: "run-a76d-8eab", sequence_num: 4, event_type: "step_completed", step_id: "verify_checksums", timestamp: "2026-10-21T04:01:48Z" },
      { id: "evt-25", run_id: "run-a76d-8eab", sequence_num: 5, event_type: "run_completed", timestamp: "2026-10-21T04:01:48Z" },
    ],
  },
];
