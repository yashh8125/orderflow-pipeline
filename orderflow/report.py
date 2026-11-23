"""Run the analytics SQL against the warehouse and save each result as a CSV."""

import re
from pathlib import Path

import pandas as pd
from sqlalchemy import Engine, text

SQL_FILE = Path(__file__).with_name("analytics.sql")


def load_queries(sql_file: Path = SQL_FILE) -> dict[str, str]:
    blocks = re.split(r"^-- name:\s*(\w+)\s*$", sql_file.read_text(encoding="utf-8"), flags=re.M)
    # re.split gives [preamble, name1, body1, name2, body2, ...]
    return {name: body.strip() for name, body in zip(blocks[1::2], blocks[2::2], strict=True)}


def run_reports(engine: Engine, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, query in load_queries().items():
        with engine.connect() as conn:
            df = pd.read_sql(text(query), conn)
        path = out_dir / f"{name}.csv"
        df.to_csv(path, index=False)
        written.append(path)
    return written
