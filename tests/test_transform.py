import pandas as pd
import pytest

from orderflow import transform


@pytest.fixture
def products():
    return pd.DataFrame({"product_id": ["P001", "P002"], "price": [10.0, 25.5],
                         "name": ["A", "B"], "category": ["Books", "Home"]})


@pytest.fixture
def customers():
    return pd.DataFrame({"customer_id": ["C0001", "C0002"]})


def make_orders(**overrides):
    row = {"order_id": "O1", "customer_id": "C0001", "product_id": "P001", "quantity": "2",
           "unit_price": "$10.00", "order_date": "2025-03-01", "status": "Completed "}
    row.update(overrides)
    return pd.DataFrame([row])


def clean(df, products, customers):
    return transform.clean_orders(df, products, customers)


def test_valid_row_is_cleaned(products, customers):
    good, rejected = clean(make_orders(), products, customers)
    assert rejected.empty
    row = good.iloc[0]
    assert row["unit_price"] == 10.0 and row["quantity"] == 2
    assert row["total_amount"] == 20.0
    assert row["status"] == "completed"
    assert row["order_month"] == "2025-03"


def test_missing_price_is_filled_from_catalogue(products, customers):
    good, _ = clean(make_orders(unit_price=None, product_id="P002"), products, customers)
    assert good.iloc[0]["unit_price"] == 25.5


def test_mixed_date_formats_are_parsed(products, customers):
    df = pd.concat([
        make_orders(order_id="O1", order_date="2025-03-01"),
        make_orders(order_id="O2", order_date="2025/03/02"),
        make_orders(order_id="O3", order_date="Mar 03, 2025"),
    ], ignore_index=True)
    good, rejected = clean(df, products, customers)
    assert rejected.empty
    assert sorted(good["order_date"].astype(str)) == ["2025-03-01", "2025-03-02", "2025-03-03"]


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"quantity": "-1"}, "invalid_quantity"),
        ({"quantity": None}, "invalid_quantity"),
        ({"quantity": "1.5"}, "invalid_quantity"),
        ({"customer_id": None}, "missing_customer_id"),
        ({"customer_id": "C9999"}, "unknown_customer"),
        ({"product_id": "P999", "unit_price": "5"}, "unknown_product"),
        ({"order_date": "not a date"}, "invalid_date"),
        ({"status": "teleported"}, "invalid_status"),
        ({"unit_price": "abc", "product_id": "P001"}, None),  # recovered from catalogue
    ],
)
def test_invalid_rows_are_rejected_with_reason(products, customers, overrides, reason):
    good, rejected = clean(make_orders(**overrides), products, customers)
    if reason is None:
        assert len(good) == 1 and rejected.empty
    else:
        assert good.empty
        assert rejected.iloc[0]["reject_reason"] == reason


def test_duplicate_order_ids_keep_last_and_reject_earlier(products, customers):
    df = pd.concat([make_orders(quantity="1"), make_orders(quantity="3")], ignore_index=True)
    good, rejected = clean(df, products, customers)
    assert len(good) == 1 and good.iloc[0]["quantity"] == 3
    assert rejected.iloc[0]["reject_reason"] == "duplicate_order_id"


def test_customers_normalised_and_deduplicated():
    raw = pd.DataFrame({
        "customer_id": ["C1", "C1", "C2"],
        "name": ["Ann", "Ann B", "Bob"],
        "email": ["ANN@Example.com", "ann@example.com", "not-an-email"],
        "address.city": ["X", "X", "Y"],
        "address.country": ["india", "India", "Atlantis"],
        "signup_date": ["2024-01-01", "2024-01-01", "2024-02-01"],
    })
    good, rejected = transform.clean_customers(raw)
    assert len(good) == 2 and len(rejected) == 1
    by_id = good.set_index("customer_id")
    assert by_id.loc["C1", "country"] == "IN"
    assert by_id.loc["C2", "country"] == "UNKNOWN"
    assert pd.isna(by_id.loc["C2", "email"])  # invalid email nulled, customer kept
