"""Extract step: read raw files exactly as they are. No cleaning happens here."""

import json
from pathlib import Path

import pandas as pd


def read_orders(data_dir: Path) -> pd.DataFrame:
    # dtype=str keeps the raw text so validation decides what is valid, not the CSV reader.
    return pd.read_csv(data_dir / "orders.csv", dtype=str)


def read_products(data_dir: Path) -> pd.DataFrame:
    return pd.read_csv(data_dir / "products.csv", dtype=str)


def read_customers(data_dir: Path) -> pd.DataFrame:
    """customers.json is nested; json_normalize flattens it to address.city, address.country."""
    with open(data_dir / "customers.json", encoding="utf-8") as f:
        return pd.json_normalize(json.load(f))
