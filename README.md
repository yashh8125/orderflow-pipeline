![CI](https://github.com/yashh8125/orderflow-pipeline/actions/workflows/ci.yml/badge.svg)

# OrderFlow: a containerized, CI-tested ETL pipeline

A small data-engineering project with a real DevOps layer. It takes messy e-commerce order data
(CSV and nested JSON), cleans and validates it with Pandas, loads it into a warehouse
(PostgreSQL in Docker, SQLite locally) and produces SQL analytics reports.

```
 data/raw/                      orderflow (Python)                      warehouse
┌────────────────┐   ┌───────────┐   ┌─────────────────────┐   ┌──────────────────────┐
│ orders.csv     │──▶│  EXTRACT  │──▶│ TRANSFORM           │──▶│ LOAD (1 transaction) │
│ products.csv   │   │ read raw  │   │ clean + validate    │   │ upsert, idempotent   │
│ customers.json │   │ as text   │   │ rejects + reasons   │   │ dim_* / fact_orders  │
└────────────────┘   └───────────┘   └─────────────────────┘   └──────────┬───────────┘
                                                                          │
                       reports/*.csv  ◀── SQL analytics (joins, CTEs, window functions)
                       reports/rejected_*.csv  ◀── every bad row, with its reason
```

## Run it

**Quickest (no Docker, SQLite):**
```bash
pip install -r requirements.txt
python -m orderflow.pipeline --generate     # makes sample data, runs everything
python -m orderflow.pipeline                # run again: row counts do not change
```

**Full stack (PostgreSQL + pipeline in Docker):**
```bash
cp .env.example .env        # then edit the password and set APP_UID/APP_GID (id -u, id -g)
docker compose up --build   # waits for the DB healthcheck, then runs the pipeline
```

**Tests and checks (same as CI):**
```bash
pip install -r requirements-dev.txt
ruff check . && pytest -q && bandit -r orderflow -q && pip-audit -r requirements.txt
```

## What it demonstrates

### Data engineering
| Skill | Where |
|---|---|
| Structured + semi-structured data | `extract.py` (CSV, plus nested JSON flattened with `json_normalize`) |
| Cleaning and validation | `transform.py`: type coercion, `"$12.50"` strings, mixed date formats, casing, nulls, duplicates |
| Fixing instead of discarding | Missing prices recovered from the product catalogue; invalid emails nulled, customer kept |
| Rejected-record tracking | Every dropped row goes to `reports/rejected_*.csv` with a `reject_reason` |
| Warehouse schema | `load.py`: dimension tables, fact table, primary and foreign keys, indexes |
| Idempotent loads | `INSERT ... ON CONFLICT DO UPDATE`, so re-running never duplicates |
| Incremental loads | `--incremental` uses a watermark stored in `pipeline_runs` |
| Atomic loads | All three tables load in one transaction, so a failure leaves no half-loaded data |
| SQL | `analytics.sql`: JOIN, GROUP BY, CTE, `RANK`, `LAG`, running totals, % of total |
| Run auditing | `pipeline_runs` table: status, rows extracted/loaded/rejected, timings |

### DevOps / DevSecOps
| Skill | Where |
|---|---|
| Containers | `Dockerfile`: slim image, non-root user, no cache |
| Orchestration | `docker-compose.yml`: Postgres healthcheck, `depends_on: service_healthy` |
| Hardening | DB not exposed on any host port, `read_only` filesystem, `cap_drop: ALL`, `no-new-privileges` |
| Secrets | Env vars and `.env` (git-ignored); compose refuses to start if they are unset |
| CI | `ci.yml`: ruff, pytest, Bandit (SAST), pip-audit (dependencies), Docker build, Trivy image scan |
| Scheduling | `nightly.yml` (cron in GitHub Actions) or host cron: `docker compose run --rm pipeline` |
| Failure handling | Retries on DB startup, logged stack traces, exit code 1 on failure |
| Cloud | Optional `s3_sync.py` uploads reports to S3 with SSE (least-privilege IAM, `S3_BUCKET` env) |


