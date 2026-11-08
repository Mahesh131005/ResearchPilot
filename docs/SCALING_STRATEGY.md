# ResearchPilot — Infrastructure Scaling Strategy

## 1. Executive Summary & Topology Overview

ResearchPilot is designed as an asynchronous, event-driven multi-agent research platform. To scale reliably from beta to high-volume production, the architecture decouples client-facing HTTP/SSE endpoints from compute-intensive LangGraph multi-agent research execution.

### Component Topology

```
                         ┌───────────────────────┐
                         │   Edge / CDN / Proxy  │
                         │    (Cloudflare/Nginx) │
                         └───────────┬───────────┘
                                     │
                    ┌────────────────┴────────────────┐
                    │                                 │
           ┌────────▼────────┐               ┌────────▼────────┐
           │ Static Frontend │               │ FastAPI Gateway │
           │   (Nginx/SPA)   │               │   (Stateless)   │
           └─────────────────┘               └────────┬────────┘
                                                      │
                       ┌──────────────────────────────┼──────────────────────────────┐
                       │                              │                              │
              ┌────────▼────────┐            ┌────────▼────────┐            ┌────────▼────────┐
              │  PostgreSQL 16  │            │     Redis 7     │            │ Prometheus /    │
              │   + pgvector    │            │ (Queue & Cache) │            │ Observability   │
              └────────▲────────┘            └────────▲────────┘            └─────────────────┘
                       │                              │
                       │             ┌────────────────┴────────────────┐
                       │             │                                 │
                       └─────────────┼──────────────────┐              │
                                     │                  │              │
                            ┌────────▼────────┐┌────────▼────────┐┌────▼───────────┐
                            │ LangGraph Worker││ LangGraph Worker││ LangGraph Worker│
                            │   Instance #1   ││   Instance #2   ││   Instance #N   │
                            └─────────────────┘└─────────────────┘└─────────────────┘
```

---

## 2. Component Scaling Characteristics

| Component | Nature | Primary Scaling Bottlenecks | Scaling Mechanism |
| :--- | :--- | :--- | :--- |
| **FastAPI Gateway** | Stateless | Concurrency, TLS termination, JSON serialization | Horizontal Pod Autoscaling (HPA) via CPU / Request rate |
| **LangGraph Workers** | Stateful Execution | Provider rate limits, LLM latency, Memory RSS | Queue-depth autoscaling (KEDA) |
| **PostgreSQL 16** | Stateful Relational | Connection limits, Disk I/O, Vector index build | PgBouncer multiplexing, read replicas, storage IOPS |
| **Redis 7** | Stateful In-Memory | Memory limits, network saturation | Redis Cluster / Sentinel with persistence (AOF/RDB) |

---

## 3. Database Connection Pooling & Sizing

In high-concurrency deployments with multiple FastAPI replicas and distributed LangGraph workers, unmanaged PostgreSQL connections can rapidly exhaust PostgreSQL's `max_connections` limit.

### Configuration Strategy

1. **FastAPI Web Instances**:
   - `pool_size`: 10 connections per worker process.
   - `max_overflow`: 5 transient overflow connections.
   - `pool_recycle`: 1800 seconds (30 minutes) to eliminate stale socket connections.
   - `pool_pre_ping`: Enabled (`SELECT 1` ping before checkout) to guarantee connection liveness.

2. **PgBouncer Integration**:
   - For deployments exceeding 5 application replicas, deploy PgBouncer in transaction-pooling mode (`pool_mode = transaction`).
   - Allows thousands of client connections to share 50–100 physical PostgreSQL backend connections.
   - Note: Prepared statements and transaction-level advisory locks must be configured to ensure compatibility with asyncpg in transaction pooling mode.

3. **pgvector Scaling**:
   - **Index Type**: Migrate from default sequential scan to **HNSW** (`vector_cosine_ops`) once chunk count exceeds 25,000.
   - **HNSW Parameters**: `m = 16`, `ef_construction = 64` for balanced indexing speed and recall accuracy.
   - **Maintenance Work Mem**: Allocate `maintenance_work_mem = 512MB` for parallel index builds.

---

## 4. Worker Autoscaling & Queue Management

### Decoupling Scaling from Monetary Controls
> [!IMPORTANT]
> **Worker autoscaling must NEVER bypass user rate limits, quotas, or global spending caps.**
> Horizontal autoscaling scales execution capacity, but admissions control occurs strictly at the FastAPI Gateway layer *before* jobs enter the queue.

### Scaling Criteria
Workers are autoscaled horizontally using **KEDA (Kubernetes Event-driven Autoscaling)** or Docker Swarm metrics based on:
1. **Redis Queue Depth**: If unprocessed jobs in `research:jobs:queued` > 5 per worker for 60 seconds, scale up +1 worker.
2. **Average Job Wait Time**: If time from job submission to agent start exceeds 30 seconds, trigger proactive scaling.
3. **Scale-Down Stabilization**: Apply a 300-second scale-down cooldown window to prevent thrashing during bursty research cycles.

---

## 5. Graceful Shutdown & Failure Recovery

### In-Flight Job Protection
When a worker node is marked for termination (e.g., node drain, deployment rollout, or spot instance reclamation):

1. **SIGTERM Interception**: The worker stops accepting new jobs from Redis.
2. **Graceful Drain Window**: The worker is granted `GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS = 15` (configurable up to 60s in Kubernetes `terminationGracePeriodSeconds`) to finish or checkpoint in-flight research steps.
3. **Durable Leases & Crash Recovery**:
   - Every active research job has a renewable worker lease stored in Redis (`job:lease:<job_id>`).
   - If a worker crashes abruptly or is killed by OOM, the lease expires after 120 seconds.
   - The queue monitor detects abandoned jobs with expired leases and moves them back to `queued` with an incremented retry counter (max 3 retries).
   - Permanent failures are recorded with status `failed` and an informative error message.

---

## 6. Docker Compose Multi-Instance Scaling

For staging, enterprise on-premise, or local testing, ResearchPilot's `docker-compose.yml` supports multi-replica scaling directly:

```bash
# Start infrastructure and scale backend to 3 replicas
docker-compose up -d --scale backend=3
```

All services enforce strict container resource constraints (`deploy.resources.limits`) to prevent runaway container memory or CPU starvation:
- **Backend**: 1.5 CPU cores, 1.5GB RAM
- **Postgres 16**: 2.0 CPU cores, 2.0GB RAM
- **Redis 7**: 0.5 CPU cores, 512MB RAM
- **Frontend**: 0.5 CPU cores, 256MB RAM

