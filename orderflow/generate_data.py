"""Generate deliberately messy sample data (CSV + nested JSON) so the pipeline has real work to do.

Problems injected on purpose: duplicate rows, nulls, negative quantities, prices as "$12.50"
strings, mixed date formats, inconsistent casing, unknown customers, invalid emails.
"""

import json
import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

CATEGORIES = ["Electronics", "Books", "Home", "Fashion", "Sports"]
CITIES = ["Ahmedabad", "Mumbai", "London", "Berlin", "New York", "Austin"]
COUNTRIES = ["India", "IN", "india", "USA", "US", "United States", "UK", "United Kingdom",
             "Germany", "DE"]
STATUSES = ["completed"] * 6 + ["Completed ", " COMPLETED", "pending", "cancelled", "canceled",
                                "refunded"]
DATE_FORMATS = ["%Y-%m-%d", "%Y/%m/%d", "%b %d, %Y"]


def generate(out_dir: str | Path, n_orders: int = 2000, seed: int = 42) -> Path:
    # Sample data only, so a seeded non-cryptographic RNG is fine here.
    rng = random.Random(seed)  # noqa: S311  # nosec B311
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    products = [
        {
            "product_id": f"P{i:03d}",
            "name": f"Product {i}",
            "category": CATEGORIES[i % len(CATEGORIES)],
            "price": round(rng.uniform(5, 300), 2),
        }
        for i in range(1, 41)
    ]
    pd.DataFrame(products).to_csv(out / "products.csv", index=False)

    customers = []
    for i in range(1, 301):
        email = f"user{i}@example.com"
        if rng.random() < 0.05:
            email = f"user{i}.example.com"  # invalid on purpose
        customers.append(
            {
                "customer_id": f"C{i:04d}",
                "name": f"Customer {i}",
                "email": email,
                "address": {"city": rng.choice(CITIES), "country": rng.choice(COUNTRIES)},
                "signup_date": (date(2024, 1, 1) + timedelta(days=rng.randint(0, 365))).isoformat(),
            }
        )
    customers += rng.sample(customers, 10)  # duplicated customers
    (out / "customers.json").write_text(json.dumps(customers, indent=2), encoding="utf-8")

    start = date(2025, 1, 1)
    rows = []
    for i in range(1, n_orders + 1):
        product = rng.choice(products)
        order_date = start + timedelta(days=rng.randint(0, 330))
        price = f"${product['price']:.2f}" if rng.random() < 0.3 else product["price"]
        row = {
            "order_id": f"O{i:06d}",
            "customer_id": f"C{rng.randint(1, 300):04d}",
            "product_id": product["product_id"],
            "quantity": rng.randint(1, 5),
            "unit_price": price,
            "order_date": order_date.strftime(rng.choice(DATE_FORMATS)),
            "status": rng.choice(STATUSES),
        }
        roll = rng.random()
        if roll < 0.02:
            row["customer_id"] = None
        elif roll < 0.04:
            row["customer_id"] = "C9999"  # unknown customer
        elif roll < 0.06:
            row["quantity"] = -rng.randint(1, 3)
        elif roll < 0.07:
            row["quantity"] = None
        elif roll < 0.12:
            row["unit_price"] = None  # recoverable from the products table
        elif roll < 0.13:
            row["order_date"] = "not a date"
        rows.append(row)

    rows += rng.sample(rows, int(n_orders * 0.03))  # exact duplicate rows
    rng.shuffle(rows)
    pd.DataFrame(rows).to_csv(out / "orders.csv", index=False)
    return out


if __name__ == "__main__":
    print(f"Sample data written to {generate('data/raw')}")
