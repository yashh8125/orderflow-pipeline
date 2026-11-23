"""Transform step: clean, standardise and validate. Each function returns (clean, rejected).

Rejected rows keep their original raw values plus a `reject_reason`, so nothing is silently
dropped and every bad record can be traced back to its cause.
"""

import pandas as pd

COUNTRY_MAP = {
    "india": "IN", "in": "IN",
    "usa": "US", "us": "US", "united states": "US",
    "uk": "GB", "gb": "GB", "united kingdom": "GB",
    "germany": "DE", "de": "DE",
}
STATUS_MAP = {
    "completed": "completed", "complete": "completed",
    "pending": "pending",
    "cancelled": "cancelled", "canceled": "cancelled",
    "refunded": "refunded",
}
EMAIL_RE = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

PRODUCT_COLS = ["product_id", "name", "category", "price"]
CUSTOMER_COLS = ["customer_id", "name", "email", "city", "country", "signup_date"]
ORDER_COLS = ["order_id", "customer_id", "product_id", "quantity", "unit_price", "total_amount",
              "status", "order_date", "order_month"]


def _reasons(index: pd.Index, checks: dict[str, pd.Series]) -> pd.Series:
    """Return the first failing check name per row ('' means the row is valid)."""
    reason = pd.Series("", index=index, dtype=object)
    for name, failed in checks.items():
        failed = failed.fillna(False).astype(bool)
        reason[(reason == "") & failed] = name
    return reason


def _blank(s: pd.Series) -> pd.Series:
    return s.isna() | (s == "")


def clean_products(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    d = df.copy()
    for col in ("product_id", "name", "category"):
        d[col] = d[col].str.strip()
    d["price"] = pd.to_numeric(d["price"], errors="coerce")
    reason = _reasons(d.index, {
        "missing_product_id": _blank(d["product_id"]),
        "invalid_price": d["price"].isna() | (d["price"] <= 0),
        "duplicate_product_id": d["product_id"].duplicated(keep="last"),
    })
    rejected = df[reason != ""].assign(reject_reason=reason[reason != ""])
    return d[reason == ""][PRODUCT_COLS].reset_index(drop=True), rejected


def clean_customers(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    d = df.rename(columns={"address.city": "city", "address.country": "country"}).copy()
    for col in ("customer_id", "name", "email", "city", "country"):
        d[col] = d[col].str.strip()
    d["email"] = d["email"].str.lower()
    # An invalid email should not cost us the customer: null the field, keep the row.
    bad_email = ~d["email"].str.match(EMAIL_RE).fillna(False).astype(bool)
    d.loc[bad_email, "email"] = None
    d["country"] = d["country"].str.lower().map(COUNTRY_MAP).fillna("UNKNOWN")
    d["signup_date"] = pd.to_datetime(d["signup_date"], errors="coerce").dt.date

    reason = _reasons(d.index, {
        "missing_customer_id": _blank(d["customer_id"]),
        "missing_name": _blank(d["name"]),
        "duplicate_customer_id": d["customer_id"].duplicated(keep="last"),
    })
    rejected = df[reason != ""].assign(reject_reason=reason[reason != ""])
    return d[reason == ""][CUSTOMER_COLS].reset_index(drop=True), rejected


def clean_orders(
    df: pd.DataFrame, products: pd.DataFrame, customers: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    d = df.copy()
    for col in ("order_id", "customer_id", "product_id", "status"):
        d[col] = d[col].str.strip()

    d["quantity"] = pd.to_numeric(d["quantity"], errors="coerce")
    price_text = d["unit_price"].astype(str).str.replace(r"[$,\s]", "", regex=True)
    d["unit_price"] = pd.to_numeric(price_text, errors="coerce")
    # Missing price? Recover it from the product catalogue instead of throwing the order away.
    catalogue = products.set_index("product_id")["price"]
    d["unit_price"] = d["unit_price"].fillna(d["product_id"].map(catalogue))
    d["order_date"] = pd.to_datetime(d["order_date"], format="mixed", errors="coerce")
    d["status"] = d["status"].str.lower().map(STATUS_MAP)

    reason = _reasons(d.index, {
        "missing_order_id": _blank(d["order_id"]),
        "duplicate_order_id": d["order_id"].duplicated(keep="last") & ~_blank(d["order_id"]),
        "missing_customer_id": _blank(d["customer_id"]),
        "unknown_customer": ~d["customer_id"].isin(customers["customer_id"]),
        "unknown_product": ~d["product_id"].isin(products["product_id"]),
        "invalid_quantity": d["quantity"].isna() | (d["quantity"] <= 0) | (d["quantity"] % 1 != 0),
        "invalid_price": d["unit_price"].isna() | (d["unit_price"] <= 0),
        "invalid_date": d["order_date"].isna(),
        "invalid_status": d["status"].isna(),
    })

    good = d[reason == ""].copy()
    good["quantity"] = good["quantity"].astype(int)
    good["total_amount"] = (good["quantity"] * good["unit_price"]).round(2)
    good["order_month"] = good["order_date"].dt.strftime("%Y-%m")
    good["order_date"] = good["order_date"].dt.date
    rejected = df[reason != ""].assign(reject_reason=reason[reason != ""])
    return good[ORDER_COLS].reset_index(drop=True), rejected
