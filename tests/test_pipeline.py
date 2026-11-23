import pandas as pd
from sqlalchemy import create_engine, text

from orderflow import pipeline
from orderflow.generate_data import generate


def count(url: str, table: str) -> int:
    with create_engine(url).connect() as conn:
        return conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()  # noqa: S608


def test_pipeline_is_idempotent_and_writes_reports(tmp_path):
    data, reports = tmp_path / "raw", tmp_path / "reports"
    url = f"sqlite:///{tmp_path / 'wh.db'}"
    generate(data, n_orders=500)

    first = pipeline.run(data, reports, url)
    orders_after_first = count(url, "fact_orders")
    second = pipeline.run(data, reports, url)

    assert orders_after_first > 0
    assert count(url, "fact_orders") == orders_after_first  # re-run adds no duplicates
    assert first["rows_loaded"] == second["rows_loaded"]
    assert count(url, "pipeline_runs") == 2

    for name in ("revenue_by_month", "top_customers", "category_performance", "rejected_orders"):
        assert (reports / f"{name}.csv").exists()
    rejected = pd.read_csv(reports / "rejected_orders.csv")
    assert {"reject_reason"} <= set(rejected.columns) and len(rejected) > 0


def test_incremental_run_loads_nothing_new_when_data_unchanged(tmp_path):
    data, reports = tmp_path / "raw", tmp_path / "reports"
    url = f"sqlite:///{tmp_path / 'wh.db'}"
    generate(data, n_orders=300)
    pipeline.run(data, reports, url)
    before = count(url, "fact_orders")
    pipeline.run(data, reports, url, incremental=True)
    assert count(url, "fact_orders") == before


def test_failure_returns_nonzero_exit_code(tmp_path):
    code = pipeline.main(["--data-dir", str(tmp_path / "missing"),
                          "--report-dir", str(tmp_path / "r"),
                          "--database-url", f"sqlite:///{tmp_path / 'x.db'}"])
    assert code == 1
