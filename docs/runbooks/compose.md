# Fieldkit Production Docker Compose Runbook

**Audience**: Plant IT & OT Infrastructure Administrators (Tobias Becker, Halden Industrie)  
**Applies To**: Single-server On-Premises & Air-Gapped Deployments  
**Classification**: Internal Operations Runbook  

---

## 1. System Architecture & Resource Baseline

Fieldkit runs as a modular Docker Compose application with profiles tailored for memory-constrained industrial workstations and server racks (16 GB to 64 GB RAM, x86_64 CPU).

### Resource Allocations per Container Profile

| Service / Profile | Default Port | Memory Limit | CPU Limit | Storage Mount |
| :--- | :---: | :---: | :---: | :--- |
| **`postgres` (core)** | 5432 | 2048 MB | 2.0 | `postgres_data` (Named volume) |
| **`redis` (core)** | 6379 | 512 MB | 1.0 | `redis_data` (Named volume) |
| **`minio` (foundry/docai/inspect)** | 9000, 9001 | 1024 MB | 1.0 | `minio_data` (Named volume) |
| **`clickhouse` (observe/vision)** | 8123, 9000 | 2048 MB | 2.0 | `clickhouse_data` (Named volume) |
| **`keycloak` (core)** | 8080 | 1024 MB | 1.5 | `../keycloak` (Realm import) |
| **`workflow-engine` (workflow)** | 8008 | 512 MB | 1.0 | Stateless (PostgreSQL backed) |
| **`vision-edge` (vision/inspect)** | 8005 | 2048 MB | 3.0 | Ephemeral / Frame queues |
| **`console` (all)** | 3000 | 1024 MB | 2.0 | Next.js Node process |

---

## 2. Preflight Installation & Launch Procedure

### 2.1 Environment Configuration
Ensure `.env` exists at the root of the repository. A default template is provided in `.env.example`:
```bash
cp .env.example .env
```
Ensure all required ports (`5432`, `6379`, `8080`, `8001`-`8008`, `9000`, `9001`) are unblocked on the host firewall.

### 2.2 Launching Core Services & Desired Profile
```bash
# Start core persistence (PostgreSQL + pgvector, Redis, Keycloak)
make up P=core

# Start with Workflow Engine & Inspection Services
make up P=workflow

# Start all platform services
make up P=all
```

---

## 3. Readiness & Health Verification

Fieldkit includes a deterministic readiness smoke testing tool that verifies health and ready probes (`/healthz`, `/readyz`, database connectivity) across all active services:

```bash
# Run multi-service health and readiness smoke test
uv run python scripts/smoke_readiness.py
```

Expected output:
```text
[READY] postgres (port 5432) -> Healthy
[READY] redis (port 6379) -> PONG
[READY] keycloak (http://localhost:8080/health/ready) -> 200 OK
[READY] workflow-engine (http://localhost:8008/readyz) -> 200 OK
[READY] vision-edge (http://localhost:8005/readyz) -> 200 OK
```

---

## 4. Disaster Recovery & Backup Procedures

Industrial cybersecurity compliance requires daily automated backups and verified restore capability.

### 4.1 Creating an Offline Snapshot (`scripts/backup.py` / `make backup`)
The backup tool extracts:
1. **PostgreSQL Relational & Vector Ledger**: Custom binary format (`pg_dump -Fc`) containing schema, vector embeddings, and audit trails.
2. **MinIO Object Store**: Mirror of all inspection heatmaps, PDF raw documents, and manifests.
3. **Metadata Manifest**: SHA-256 fingerprint, timestamp, and container image versions saved into `./backups/<YYYYMMDD-HHMMSS>/`.

```bash
# Trigger automated point-in-time backup
make backup
# OR
uv run python scripts/backup.py --target ./backups
```

### 4.2 Restoring from Snapshot (`scripts/restore.py` / `make restore`)

#### Step 1: Dry-Run Inspection
Always run with `--dry-run` to inspect backup archive checksums, table inventory, and disk requirements without applying mutations:
```bash
uv run python scripts/restore.py --archive ./backups/20261021-120000 --dry-run
```

#### Step 2: Executing Restoration
```bash
uv run python scripts/restore.py --archive ./backups/20261021-120000 --confirm
```

---

## 5. Troubleshooting & Failure Recovery

### 5.1 Disk Fullness Emergency (MinIO / ClickHouse)
If plant sensors or continuous video analysis fill local disks past 85%:
```bash
# Check Docker named volume disk usage
docker system df -v

# Prune stale intermediate container layers
docker image prune -f
```

### 5.2 Workflow Engine Unscheduled Process Crash
The Go workflow engine is event-sourced and crash-resilient:
1. If the engine process terminates, restart the container:
   ```bash
   docker compose -f deploy/compose/docker-compose.yml restart workflow-engine
   ```
2. Any task whose lease expired (`lease_until < NOW()`) is automatically re-queued and leased by the recovered worker pool.
3. Downstream services receive the same `X-Idempotency-Key: <run_id>:<step_id>`, guaranteeing zero duplicate side-effects.
