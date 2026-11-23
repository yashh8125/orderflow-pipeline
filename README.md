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

## Design decisions (good interview material)

- **Why read everything as text?** `dtype=str` means validation, not the CSV parser, decides what is a number or a date.
- **Why upsert instead of truncate-and-reload?** It's safe to re-run, supports late-arriving corrections and never leaves the table empty.
- **Why one transaction?** If the orders load fails, the dimension rows roll back too.
- **Why keep rejects?** In production you must be able to answer "which records did we drop and why?"
- **Known limitations:** upsert is implemented for SQLite and PostgreSQL only; date formats like `05/03/2025` are ambiguous and need a decision from the data owner (the sample data avoids them); `--incremental` assumes new orders are not back-dated before the previous max date.
- **Untested here:** the S3 upload and the Docker/Trivy/Actions workflows need your environment (Docker, AWS credentials, a GitHub repo). The Python pipeline, tests, lint and Bandit were run.

## Ideas to extend it (pick one or two)
1. Add a data-quality gate: fail the run if more than 10% of orders are rejected.
2. Replace `nightly.yml` with Airflow or cron inside a container.
3. Add Terraform for the S3 bucket and IAM policy.
4. Add a Grafana or Metabase container reading from Postgres.

## Resume bullets (use only what you actually built and can explain)
- Built a containerized ETL pipeline (Python, Pandas, SQLAlchemy, PostgreSQL, Docker Compose) that cleans and validates CSV and nested JSON order data, with idempotent upserts, incremental loads and rejected-record tracking.
- Designed a star-style warehouse schema and SQL analytics (joins, CTEs, window functions) producing automated revenue, customer and category reports.
- Implemented CI/CD in GitHub Actions with linting, unit and integration tests, Bandit, pip-audit and Trivy scans, plus scheduled nightly runs; hardened containers (non-root, read-only, dropped capabilities).
