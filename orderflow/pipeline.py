"""Pipeline entry point: extract -> transform -> load -> report.

Run with:  python -m orderflow.pipeline --generate
Exit code is 0 on success and 1 on failure, so cron, Docker and CI can all detect problems.
"""

import argparse
import logging
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

from orderflow import config, extract, load, report, s3_sync, transform
from orderflow.generate_data import generate

log = logging.getLogger("orderflow")


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def with_retry(fn, attempts: int = 5, delay: float = 2.0):
    """Retry on transient database connection errors (e.g. Postgres still starting up)."""
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except OperationalError:
            if attempt == attempts:
                raise
            log.warning("Database not ready (attempt %d/%d), retrying", attempt, attempts)
            time.sleep(delay * attempt)


def _save_rejects(report_dir: Path, name: str, rejected) -> None:
    rejected.to_csv(report_dir / f"rejected_{name}.csv", index=False)
    if len(rejected):
        counts = rejected["reject_reason"].value_counts().to_dict()
        log.info("Rejected %d %s rows: %s", len(rejected), name, counts)


def run(data_dir: Path, report_dir: Path, database_url: str, incremental: bool = False) -> dict:
    started = _utcnow()
    engine = create_engine(database_url, pool_pre_ping=True)
    stats = {"rows_extracted": 0, "rows_loaded": 0, "rows_rejected": 0, "max_order_date": None}
    report_dir.mkdir(parents=True, exist_ok=True)

    try:
        with_retry(lambda: load.init_schema(engine))

        # Extract
        orders_raw = extract.read_orders(data_dir)
        products_raw = extract.read_products(data_dir)
        customers_raw = extract.read_customers(data_dir)
        stats["rows_extracted"] = len(orders_raw)
        log.info("Extracted %d orders, %d products, %d customers",
                 len(orders_raw), len(products_raw), len(customers_raw))

        # Transform
        products, rej_products = transform.clean_products(products_raw)
        customers, rej_customers = transform.clean_customers(customers_raw)
        orders, rej_orders = transform.clean_orders(orders_raw, products, customers)
        stats["rows_rejected"] = len(rej_orders)
        for name, rejected in (("products", rej_products), ("customers", rej_customers),
                               ("orders", rej_orders)):
            _save_rejects(report_dir, name, rejected)

        if incremental:
            watermark = load.get_watermark(engine)
            if watermark is not None:
                orders = orders[orders["order_date"] >= watermark]
                log.info("Incremental mode: keeping orders on or after %s", watermark)

        # Load: one transaction, so a failure halfway leaves the warehouse untouched.
        with engine.begin() as conn:
            load.upsert(conn, load.dim_products, products, "product_id")
            load.upsert(conn, load.dim_customers, customers, "customer_id")
            stats["rows_loaded"] = load.upsert(conn, load.fact_orders, orders, "order_id")
        if len(orders):
            stats["max_order_date"] = max(orders["order_date"])
        log.info("Loaded %d orders", stats["rows_loaded"])

        # Report
        files = report.run_reports(engine, report_dir)
        log.info("Wrote %d analytics reports to %s", len(files), report_dir)
        if config.S3_BUCKET:
            s3_sync.upload_dir(report_dir, config.S3_BUCKET, config.S3_PREFIX)
    except Exception:
        _record(engine, started, "failed", stats)
        raise

    _record(engine, started, "success", stats)
    return stats


def _record(engine, started: datetime, status: str, stats: dict) -> None:
    try:
        load.record_run(engine, started, status, finished_at=_utcnow(), **stats)
    except Exception:
        log.exception("Could not write run record")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OrderFlow ETL pipeline")
    parser.add_argument("--data-dir", type=Path, default=config.DATA_DIR)
    parser.add_argument("--report-dir", type=Path, default=config.REPORT_DIR)
    parser.add_argument("--database-url", default=config.DATABASE_URL)
    parser.add_argument("--incremental", action="store_true",
                        help="only load orders on or after the last successful run's max date")
    parser.add_argument("--generate", action="store_true",
                        help="create sample data first if the data directory has none")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    try:
        if args.generate and not (args.data_dir / "orders.csv").exists():
            generate(args.data_dir)
            log.info("Generated sample data in %s", args.data_dir)
        run(args.data_dir, args.report_dir, args.database_url, args.incremental)
    except Exception:
        log.exception("Pipeline failed")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
