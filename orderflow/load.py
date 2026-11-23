"""Load step: schema definition and idempotent upserts into SQLite or PostgreSQL."""

from datetime import date, datetime

import pandas as pd
from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Engine,
    ForeignKey,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    func,
    insert,
    select,
)

metadata = MetaData()

dim_customers = Table(
    "dim_customers", metadata,
    Column("customer_id", String(20), primary_key=True),
    Column("name", String(100), nullable=False),
    Column("email", String(255)),
    Column("city", String(100)),
    Column("country", String(20)),
    Column("signup_date", Date),
)

dim_products = Table(
    "dim_products", metadata,
    Column("product_id", String(20), primary_key=True),
    Column("name", String(100), nullable=False),
    Column("category", String(50)),
    Column("price", Numeric(10, 2, asdecimal=False), nullable=False),
)

fact_orders = Table(
    "fact_orders", metadata,
    Column("order_id", String(20), primary_key=True),
    Column("customer_id", String(20), ForeignKey("dim_customers.customer_id"), nullable=False),
    Column("product_id", String(20), ForeignKey("dim_products.product_id"), nullable=False),
    Column("quantity", Integer, nullable=False),
    Column("unit_price", Numeric(10, 2, asdecimal=False), nullable=False),
    Column("total_amount", Numeric(12, 2, asdecimal=False), nullable=False),
    Column("status", String(20), nullable=False),
    Column("order_date", Date, nullable=False, index=True),
    Column("order_month", String(7), nullable=False, index=True),
)

pipeline_runs = Table(
    "pipeline_runs", metadata,
    Column("run_id", Integer, primary_key=True, autoincrement=True),
    Column("started_at", DateTime, nullable=False),
    Column("finished_at", DateTime, nullable=False),
    Column("status", String(10), nullable=False),
    Column("rows_extracted", Integer, nullable=False),
    Column("rows_loaded", Integer, nullable=False),
    Column("rows_rejected", Integer, nullable=False),
    Column("max_order_date", Date),
)


def init_schema(engine: Engine) -> None:
    metadata.create_all(engine)


def _records(df: pd.DataFrame) -> list[dict]:
    return df.astype(object).where(df.notna(), None).to_dict("records")


def upsert(conn, table: Table, df: pd.DataFrame, key: str) -> int:
    """INSERT ... ON CONFLICT DO UPDATE, so re-running the pipeline never duplicates rows."""
    if df.empty:
        return 0
    dialect = conn.dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as dialect_insert
    elif dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as dialect_insert
    else:
        raise NotImplementedError(f"Upsert is implemented for SQLite and PostgreSQL, not {dialect}")
    stmt = dialect_insert(table)
    stmt = stmt.on_conflict_do_update(
        index_elements=[key],
        set_={c.name: stmt.excluded[c.name] for c in table.columns if c.name != key},
    )
    conn.execute(stmt, _records(df))
    return len(df)


def get_watermark(engine: Engine) -> date | None:
    """Latest order_date seen by the last successful run (used for incremental loads)."""
    q = select(func.max(pipeline_runs.c.max_order_date)).where(pipeline_runs.c.status == "success")
    with engine.connect() as conn:
        return conn.execute(q).scalar()


def record_run(engine: Engine, started_at: datetime, status: str, rows_extracted: int,
               rows_loaded: int, rows_rejected: int, max_order_date: date | None,
               finished_at: datetime) -> None:
    with engine.begin() as conn:
        conn.execute(insert(pipeline_runs).values(
            started_at=started_at, finished_at=finished_at, status=status,
            rows_extracted=rows_extracted, rows_loaded=rows_loaded,
            rows_rejected=rows_rejected, max_order_date=max_order_date,
        ))
