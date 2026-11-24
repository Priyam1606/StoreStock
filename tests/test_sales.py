import sqlite3
import threading
from fastapi.testclient import TestClient
from app.db import get_connection
from app.main import app


def insert_customer(
    temp_db: str,
    name: str = "Test Customer",
    credit_limit_paise: int = 10000,
    active: int = 1,
    phone: str | None = None,
) -> int:
    conn = get_connection(temp_db)
    cursor = conn.execute(
        "INSERT INTO customers (name, phone, credit_limit_paise, active, created_at) VALUES (?, ?, ?, ?, '2026-01-01T00:00:00Z')",
        (name, phone, credit_limit_paise, active),
    )
    cust_id = int(cursor.lastrowid)
    conn.close()
    return cust_id


def test_selling_more_than_available_stock_returns_409(
    client: TestClient,
    owner_headers: dict[str, str],
    temp_db: str,
) -> None:
    prod_res = client.post(
        "/products",
        json={"sku": "OVERSELL_TEST", "name": "Oversell Item", "unit": "pcs", "price_paise": 1000, "cost_paise": 800},
        headers=owner_headers,
    )
    prod_id = prod_res.json()["id"]

    client.post(
        "/stock/adjustments",
        json={"product_id": prod_id, "qty_change": 5, "reason": "Initial stock"},
        headers=owner_headers,
    )

    response = client.post(
        "/sales",
        json={"payment_type": "cash", "items": [{"product_id": prod_id, "qty": 6}]},
        headers=owner_headers,
    )
    assert response.status_code == 409
    assert "Insufficient stock for product Oversell Item: requested 6, available 5" in response.json()["detail"]

    conn = get_connection(temp_db)
    sales_count = conn.execute("SELECT COUNT(*) AS total FROM sales").fetchone()["total"]
    stock_row = conn.execute(
        "SELECT COALESCE(SUM(qty_change), 0) AS stock FROM stock_movements WHERE product_id = ?",
        (prod_id,),
    ).fetchone()
    conn.close()
    assert sales_count == 0
    assert stock_row["stock"] == 5


def test_selling_exactly_available_stock_succeeds_leaves_zero(
    client: TestClient,
    owner_headers: dict[str, str],
    temp_db: str,
) -> None:
    prod_res = client.post(
        "/products",
        json={"sku": "EXACT_STOCK_TEST", "name": "Exact Item", "unit": "pcs", "price_paise": 1000, "cost_paise": 800},
        headers=owner_headers,
    )
    prod_id = prod_res.json()["id"]

    client.post(
        "/stock/adjustments",
        json={"product_id": prod_id, "qty_change": 5, "reason": "Initial stock"},
        headers=owner_headers,
    )

    response = client.post(
        "/sales",
        json={"payment_type": "cash", "items": [{"product_id": prod_id, "qty": 5}]},
        headers=owner_headers,
    )
    assert response.status_code == 201
    assert response.json()["total_paise"] == 5000

    conn = get_connection(temp_db)
    stock_row = conn.execute(
        "SELECT COALESCE(SUM(qty_change), 0) AS stock FROM stock_movements WHERE product_id = ?",
        (prod_id,),
    ).fetchone()
    conn.close()
    assert stock_row["stock"] == 0


def test_two_threads_last_unit_concurrent_sale(
    client: TestClient,
    owner_headers: dict[str, str],
    temp_db: str,
) -> None:
    prod_res = client.post(
        "/products",
        json={"sku": "LAST_UNIT_CONCURRENT", "name": "Single Unit", "unit": "pcs", "price_paise": 500, "cost_paise": 400},
        headers=owner_headers,
    )
    prod_id = prod_res.json()["id"]

    client.post(
        "/stock/adjustments",
        json={"product_id": prod_id, "qty_change": 1, "reason": "Stock 1"},
        headers=owner_headers,
    )

    results: list[int] = []
    lock = threading.Lock()

    def run_sale() -> None:
        worker_client = TestClient(app)
        res = worker_client.post(
            "/sales",
            json={"payment_type": "cash", "items": [{"product_id": prod_id, "qty": 1}]},
            headers=owner_headers,
        )
        with lock:
            results.append(res.status_code)

    t1 = threading.Thread(target=run_sale)
    t2 = threading.Thread(target=run_sale)

    t1.start()
    t2.start()

    t1.join()
    t2.join()

    assert 201 in results
    assert 409 in results
    assert len(results) == 2

    conn = get_connection(temp_db)
    stock_row = conn.execute(
        "SELECT COALESCE(SUM(qty_change), 0) AS stock FROM stock_movements WHERE product_id = ?",
        (prod_id,),
    ).fetchone()
    conn.close()
    assert stock_row["stock"] == 0


def test_sale_atomic_rollback_on_failure(
    client: TestClient,
    owner_headers: dict[str, str],
    temp_db: str,
) -> None:
    res1 = client.post(
        "/products",
        json={"sku": "ROLLBACK_1", "name": "Item 1", "unit": "pcs", "price_paise": 100, "cost_paise": 80},
        headers=owner_headers,
    )
    res2 = client.post(
        "/products",
        json={"sku": "ROLLBACK_2", "name": "Item 2", "unit": "pcs", "price_paise": 100, "cost_paise": 80},
        headers=owner_headers,
    )
    id1 = res1.json()["id"]
    id2 = res2.json()["id"]

    client.post("/stock/adjustments", json={"product_id": id1, "qty_change": 10, "reason": "Stock 1"}, headers=owner_headers)
    client.post("/stock/adjustments", json={"product_id": id2, "qty_change": 2, "reason": "Stock 2"}, headers=owner_headers)

    fail_res = client.post(
        "/sales",
        json={
            "payment_type": "cash",
            "items": [
                {"product_id": id1, "qty": 5},
                {"product_id": id2, "qty": 5},
            ],
        },
        headers=owner_headers,
    )
    assert fail_res.status_code == 409

    conn = get_connection(temp_db)
    stock1 = conn.execute("SELECT COALESCE(SUM(qty_change), 0) AS s FROM stock_movements WHERE product_id = ?", (id1,)).fetchone()["s"]
    stock2 = conn.execute("SELECT COALESCE(SUM(qty_change), 0) AS s FROM stock_movements WHERE product_id = ?", (id2,)).fetchone()["s"]
    sales_total = conn.execute("SELECT COUNT(*) AS c FROM sales").fetchone()["c"]
    conn.close()

    assert stock1 == 10
    assert stock2 == 2
    assert sales_total == 0


def test_price_change_does_not_alter_old_sales(
    client: TestClient,
    owner_headers: dict[str, str],
) -> None:
    prod_res = client.post(
        "/products",
        json={"sku": "PRICE_LOCK_TEST", "name": "Lock Item", "unit": "pcs", "price_paise": 1000, "cost_paise": 800},
        headers=owner_headers,
    )
    prod_id = prod_res.json()["id"]

    client.post("/stock/adjustments", json={"product_id": prod_id, "qty_change": 10, "reason": "Stock"}, headers=owner_headers)

    sale_res = client.post(
        "/sales",
        json={"payment_type": "cash", "items": [{"product_id": prod_id, "qty": 2}]},
        headers=owner_headers,
    )
    assert sale_res.status_code == 201
    sale_id = sale_res.json()["id"]
    assert sale_res.json()["total_paise"] == 2000

    client.patch(f"/products/{prod_id}", json={"price_paise": 2500}, headers=owner_headers)

    fetch_sale = client.get(f"/sales/{sale_id}", headers=owner_headers)
    assert fetch_sale.status_code == 200
    data = fetch_sale.json()
    assert data["total_paise"] == 2000
    assert data["items"][0]["unit_price_paise"] == 1000
    assert data["items"][0]["line_total_paise"] == 2000


def test_credit_sale_without_customer_rejected(
    client: TestClient,
    owner_headers: dict[str, str],
) -> None:
    prod_res = client.post(
        "/products",
        json={"sku": "CREDIT_NO_CUST", "name": "Credit Item", "unit": "pcs", "price_paise": 500, "cost_paise": 400},
        headers=owner_headers,
    )
    prod_id = prod_res.json()["id"]
    client.post("/stock/adjustments", json={"product_id": prod_id, "qty_change": 5, "reason": "Stock"}, headers=owner_headers)

    response = client.post(
        "/sales",
        json={"payment_type": "credit", "customer_id": None, "items": [{"product_id": prod_id, "qty": 1}]},
        headers=owner_headers,
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Customer is required for credit sale"}


def test_credit_limit_boundary(
    client: TestClient,
    owner_headers: dict[str, str],
    temp_db: str,
) -> None:
    cust_id = insert_customer(temp_db, name="Boundary Customer", credit_limit_paise=1000)

    p1 = client.post(
        "/products",
        json={"sku": "BOUNDARY_PROD_1", "name": "Item 1", "unit": "pcs", "price_paise": 1000, "cost_paise": 800},
        headers=owner_headers,
    ).json()["id"]
    p2 = client.post(
        "/products",
        json={"sku": "BOUNDARY_PROD_2", "name": "Item 2", "unit": "pcs", "price_paise": 1, "cost_paise": 0},
        headers=owner_headers,
    ).json()["id"]

    client.post("/stock/adjustments", json={"product_id": p1, "qty_change": 5, "reason": "S1"}, headers=owner_headers)
    client.post("/stock/adjustments", json={"product_id": p2, "qty_change": 5, "reason": "S2"}, headers=owner_headers)

    exact_res = client.post(
        "/sales",
        json={"payment_type": "credit", "customer_id": cust_id, "items": [{"product_id": p1, "qty": 1}]},
        headers=owner_headers,
    )
    assert exact_res.status_code == 201

    conn = get_connection(temp_db)
    bal = conn.execute("SELECT COALESCE(SUM(amount_paise), 0) AS b FROM credit_entries WHERE customer_id = ?", (cust_id,)).fetchone()["b"]
    conn.close()
    assert bal == 1000

    over_res = client.post(
        "/sales",
        json={"payment_type": "credit", "customer_id": cust_id, "items": [{"product_id": p2, "qty": 1}]},
        headers=owner_headers,
    )
    assert over_res.status_code == 409
    assert over_res.json() == {"detail": "Credit limit exceeded"}


def test_duplicate_lines_in_sale_rejected(
    client: TestClient,
    owner_headers: dict[str, str],
) -> None:
    p_id = client.post(
        "/products",
        json={"sku": "DUPE_LINE_PROD", "name": "Dupe Item", "unit": "pcs", "price_paise": 100, "cost_paise": 80},
        headers=owner_headers,
    ).json()["id"]

    res = client.post(
        "/sales",
        json={
            "payment_type": "cash",
            "items": [
                {"product_id": p_id, "qty": 1},
                {"product_id": p_id, "qty": 2},
            ],
        },
        headers=owner_headers,
    )
    assert res.status_code == 400
    assert res.json() == {"detail": "Duplicate product lines in sale"}


def test_returns_exceeding_sold_rejected(
    client: TestClient,
    owner_headers: dict[str, str],
) -> None:
    p_id = client.post(
        "/products",
        json={"sku": "RETURN_EXCEED_PROD", "name": "Ret Item", "unit": "pcs", "price_paise": 1000, "cost_paise": 800},
        headers=owner_headers,
    ).json()["id"]
    client.post("/stock/adjustments", json={"product_id": p_id, "qty_change": 10, "reason": "S"}, headers=owner_headers)

    sale = client.post(
        "/sales",
        json={"payment_type": "cash", "items": [{"product_id": p_id, "qty": 3}]},
        headers=owner_headers,
    ).json()
    sale_id = sale["id"]
    item_id = sale["items"][0]["id"]

    fail_ret = client.post(
        f"/sales/{sale_id}/returns",
        json={"items": [{"sale_item_id": item_id, "qty": 4}]},
        headers=owner_headers,
    )
    assert fail_ret.status_code == 409
    assert "Cannot return 4 units; only 3 available" in fail_ret.json()["detail"]


def test_returns_second_partial_respects_previous(
    client: TestClient,
    owner_headers: dict[str, str],
) -> None:
    p_id = client.post(
        "/products",
        json={"sku": "PARTIAL_RET_PROD", "name": "Partial Item", "unit": "pcs", "price_paise": 1000, "cost_paise": 800},
        headers=owner_headers,
    ).json()["id"]
    client.post("/stock/adjustments", json={"product_id": p_id, "qty_change": 10, "reason": "S"}, headers=owner_headers)

    sale = client.post(
        "/sales",
        json={"payment_type": "cash", "items": [{"product_id": p_id, "qty": 5}]},
        headers=owner_headers,
    ).json()
    sale_id = sale["id"]
    item_id = sale["items"][0]["id"]

    r1 = client.post(
        f"/sales/{sale_id}/returns",
        json={"items": [{"sale_item_id": item_id, "qty": 2}]},
        headers=owner_headers,
    )
    assert r1.status_code == 201

    r2 = client.post(
        f"/sales/{sale_id}/returns",
        json={"items": [{"sale_item_id": item_id, "qty": 3}]},
        headers=owner_headers,
    )
    assert r2.status_code == 201

    r3 = client.post(
        f"/sales/{sale_id}/returns",
        json={"items": [{"sale_item_id": item_id, "qty": 1}]},
        headers=owner_headers,
    )
    assert r3.status_code == 409


def test_credit_return_reduces_customer_balance(
    client: TestClient,
    owner_headers: dict[str, str],
    temp_db: str,
) -> None:
    cust_id = insert_customer(temp_db, name="Credit Return Customer", credit_limit_paise=50000)

    p_id = client.post(
        "/products",
        json={"sku": "CREDIT_RET_PROD", "name": "Cred Ret Item", "unit": "pcs", "price_paise": 2000, "cost_paise": 1500},
        headers=owner_headers,
    ).json()["id"]
    client.post("/stock/adjustments", json={"product_id": p_id, "qty_change": 10, "reason": "S"}, headers=owner_headers)

    sale = client.post(
        "/sales",
        json={"payment_type": "credit", "customer_id": cust_id, "items": [{"product_id": p_id, "qty": 3}]},
        headers=owner_headers,
    ).json()
    sale_id = sale["id"]
    item_id = sale["items"][0]["id"]

    conn = get_connection(temp_db)
    bal_before = conn.execute("SELECT COALESCE(SUM(amount_paise), 0) AS b FROM credit_entries WHERE customer_id = ?", (cust_id,)).fetchone()["b"]
    assert bal_before == 6000

    ret_res = client.post(
        f"/sales/{sale_id}/returns",
        json={"items": [{"sale_item_id": item_id, "qty": 1}]},
        headers=owner_headers,
    )
    assert ret_res.status_code == 201
    assert ret_res.json()["refund_paise"] == 2000

    bal_after = conn.execute("SELECT COALESCE(SUM(amount_paise), 0) AS b FROM credit_entries WHERE customer_id = ?", (cust_id,)).fetchone()["b"]
    stock_after = conn.execute("SELECT COALESCE(SUM(qty_change), 0) AS s FROM stock_movements WHERE product_id = ?", (p_id,)).fetchone()["s"]
    conn.close()

    assert bal_after == 4000
    assert stock_after == 8


def test_staff_can_record_sales_and_returns(
    client: TestClient,
    owner_headers: dict[str, str],
    staff_headers: dict[str, str],
) -> None:
    p_id = client.post(
        "/products",
        json={"sku": "STAFF_SALE_PROD", "name": "Staff Sale Item", "unit": "pcs", "price_paise": 1000, "cost_paise": 800},
        headers=owner_headers,
    ).json()["id"]
    client.post("/stock/adjustments", json={"product_id": p_id, "qty_change": 10, "reason": "S"}, headers=owner_headers)

    sale_res = client.post(
        "/sales",
        json={"payment_type": "cash", "items": [{"product_id": p_id, "qty": 2}]},
        headers=staff_headers,
    )
    assert sale_res.status_code == 201
    sale_id = sale_res.json()["id"]
    item_id = sale_res.json()["items"][0]["id"]

    ret_res = client.post(
        f"/sales/{sale_id}/returns",
        json={"items": [{"sale_item_id": item_id, "qty": 1}]},
        headers=staff_headers,
    )
    assert ret_res.status_code == 201


def test_get_sales_filtering(
    client: TestClient,
    owner_headers: dict[str, str],
    temp_db: str,
) -> None:
    cust1 = insert_customer(temp_db, name="Filter Cust 1", credit_limit_paise=10000)
    cust2 = insert_customer(temp_db, name="Filter Cust 2", credit_limit_paise=10000)

    p_id = client.post(
        "/products",
        json={"sku": "FILTER_SALE_PROD", "name": "Filter Sale", "unit": "pcs", "price_paise": 500, "cost_paise": 400},
        headers=owner_headers,
    ).json()["id"]
    client.post("/stock/adjustments", json={"product_id": p_id, "qty_change": 20, "reason": "S"}, headers=owner_headers)

    s1 = client.post("/sales", json={"payment_type": "credit", "customer_id": cust1, "items": [{"product_id": p_id, "qty": 1}]}, headers=owner_headers).json()["id"]
    s2 = client.post("/sales", json={"payment_type": "credit", "customer_id": cust2, "items": [{"product_id": p_id, "qty": 2}]}, headers=owner_headers).json()["id"]

    cust1_sales = client.get(f"/sales?customer_id={cust1}", headers=owner_headers)
    assert cust1_sales.status_code == 200
    ids = [s["id"] for s in cust1_sales.json()]
    assert ids == [s1]


def test_sale_huge_qty_rejected_422(
    client: TestClient,
    owner_headers: dict[str, str],
) -> None:
    res = client.post(
        "/sales",
        json={"payment_type": "cash", "items": [{"product_id": 1, "qty": 10**20}]},
        headers=owner_headers,
    )
    assert res.status_code == 422


def test_credit_sale_to_inactive_customer_rejected_409(
    client: TestClient,
    owner_headers: dict[str, str],
    temp_db: str,
) -> None:
    inactive_cust = insert_customer(temp_db, name="Inactive Cust", credit_limit_paise=10000, active=0)

    p_id = client.post(
        "/products",
        json={"sku": "INACTIVE_CUST_PROD", "name": "Item", "unit": "pcs", "price_paise": 100, "cost_paise": 80},
        headers=owner_headers,
    ).json()["id"]
    client.post("/stock/adjustments", json={"product_id": p_id, "qty_change": 10, "reason": "S"}, headers=owner_headers)

    res = client.post(
        "/sales",
        json={"payment_type": "credit", "customer_id": inactive_cust, "items": [{"product_id": p_id, "qty": 1}]},
        headers=owner_headers,
    )
    assert res.status_code == 409
    assert res.json() == {"detail": "Customer is inactive"}


def test_credit_return_can_push_balance_negative(
    client: TestClient,
    owner_headers: dict[str, str],
    temp_db: str,
) -> None:
    cust_id = insert_customer(temp_db, name="Advance Credit Cust", credit_limit_paise=10000)

    p_id = client.post(
        "/products",
        json={"sku": "ADVANCE_CREDIT_PROD", "name": "Advance Item", "unit": "pcs", "price_paise": 1000, "cost_paise": 800},
        headers=owner_headers,
    ).json()["id"]
    client.post("/stock/adjustments", json={"product_id": p_id, "qty_change": 10, "reason": "S"}, headers=owner_headers)

    sale = client.post(
        "/sales",
        json={"payment_type": "credit", "customer_id": cust_id, "items": [{"product_id": p_id, "qty": 1}]},
        headers=owner_headers,
    ).json()
    sale_id = sale["id"]
    item_id = sale["items"][0]["id"]

    conn = get_connection(temp_db)
    conn.execute(
        "INSERT INTO credit_entries (customer_id, kind, amount_paise, user_id, note, created_at) VALUES (?, 'payment', -1000, 1, 'Manual payment', '2026-01-01T00:00:00Z')",
        (cust_id,),
    )
    zero_bal = conn.execute("SELECT COALESCE(SUM(amount_paise), 0) AS b FROM credit_entries WHERE customer_id = ?", (cust_id,)).fetchone()["b"]
    assert zero_bal == 0
    conn.close()

    ret_res = client.post(
        f"/sales/{sale_id}/returns",
        json={"items": [{"sale_item_id": item_id, "qty": 1}]},
        headers=owner_headers,
    )
    assert ret_res.status_code == 201

    conn = get_connection(temp_db)
    neg_bal = conn.execute("SELECT COALESCE(SUM(amount_paise), 0) AS b FROM credit_entries WHERE customer_id = ?", (cust_id,)).fetchone()["b"]
    conn.close()
    assert neg_bal == -1000


def test_sales_date_boundaries_asia_kolkata(
    client: TestClient,
    owner_headers: dict[str, str],
    temp_db: str,
) -> None:
    conn = get_connection(temp_db)
    user_id = conn.execute("SELECT id FROM users WHERE role = 'owner'").fetchone()["id"]

    cur1 = conn.execute(
        "INSERT INTO sales (customer_id, user_id, payment_type, total_paise, created_at) VALUES (NULL, ?, 'cash', 1000, '2026-05-10T18:29:00+00:00')",
        (user_id,),
    )
    sale1_id = int(cur1.lastrowid)

    cur2 = conn.execute(
        "INSERT INTO sales (customer_id, user_id, payment_type, total_paise, created_at) VALUES (NULL, ?, 'cash', 2000, '2026-05-10T18:31:00+00:00')",
        (user_id,),
    )
    sale2_id = int(cur2.lastrowid)
    conn.close()

    day1_res = client.get("/sales?date=2026-05-10", headers=owner_headers)
    assert day1_res.status_code == 200
    day1_ids = [s["id"] for s in day1_res.json()]
    assert sale1_id in day1_ids
    assert sale2_id not in day1_ids

    day2_res = client.get("/sales?date=2026-05-11", headers=owner_headers)
    assert day2_res.status_code == 200
    day2_ids = [s["id"] for s in day2_res.json()]
    assert sale2_id in day2_ids
    assert sale1_id not in day2_ids


def test_cash_sale_with_nonexistent_customer_returns_404(
    client: TestClient,
    owner_headers: dict[str, str],
) -> None:
    prod_res = client.post(
        "/products",
        json={"sku": "CASH_CUST_404", "name": "Item 404", "unit": "pcs", "price_paise": 100, "cost_paise": 50},
        headers=owner_headers,
    )
    p_id = prod_res.json()["id"]
    client.post(
        "/stock/adjustments",
        json={"product_id": p_id, "qty_change": 10, "reason": "Stock"},
        headers=owner_headers,
    )

    res = client.post(
        "/sales",
        json={"payment_type": "cash", "customer_id": 999999, "items": [{"product_id": p_id, "qty": 1}]},
        headers=owner_headers,
    )
    assert res.status_code == 404
    assert res.json()["detail"] == "Customer not found"


def test_cash_sale_with_inactive_customer_returns_409(
    client: TestClient,
    owner_headers: dict[str, str],
    temp_db: str,
) -> None:
    cust_id = insert_customer(temp_db, name="Inactive Cust", credit_limit_paise=5000, active=0)
    prod_res = client.post(
        "/products",
        json={"sku": "CASH_CUST_409", "name": "Item 409", "unit": "pcs", "price_paise": 100, "cost_paise": 50},
        headers=owner_headers,
    )
    p_id = prod_res.json()["id"]
    client.post(
        "/stock/adjustments",
        json={"product_id": p_id, "qty_change": 10, "reason": "Stock"},
        headers=owner_headers,
    )

    res = client.post(
        "/sales",
        json={"payment_type": "cash", "customer_id": cust_id, "items": [{"product_id": p_id, "qty": 1}]},
        headers=owner_headers,
    )
    assert res.status_code == 409
    assert res.json()["detail"] == "Customer is inactive"


def test_cash_sale_with_valid_customer_succeeds(
    client: TestClient,
    owner_headers: dict[str, str],
    temp_db: str,
) -> None:
    cust_id = insert_customer(temp_db, name="Active Cash Cust", credit_limit_paise=5000, active=1)
    prod_res = client.post(
        "/products",
        json={"sku": "CASH_CUST_OK", "name": "Item OK", "unit": "pcs", "price_paise": 100, "cost_paise": 50},
        headers=owner_headers,
    )
    p_id = prod_res.json()["id"]
    client.post(
        "/stock/adjustments",
        json={"product_id": p_id, "qty_change": 10, "reason": "Stock"},
        headers=owner_headers,
    )

    res = client.post(
        "/sales",
        json={"payment_type": "cash", "customer_id": cust_id, "items": [{"product_id": p_id, "qty": 1}]},
        headers=owner_headers,
    )
    assert res.status_code == 201
    assert res.json()["customer_id"] == cust_id


def test_sale_with_more_than_200_items_rejected_400(
    client: TestClient,
    owner_headers: dict[str, str],
) -> None:
    items = [{"product_id": i, "qty": 1} for i in range(1, 202)]
    res = client.post(
        "/sales",
        json={"payment_type": "cash", "items": items},
        headers=owner_headers,
    )
    assert res.status_code == 400
    assert res.json()["detail"] == "Sale cannot contain more than 200 items"


def test_sale_total_above_10_pow_12_rejected_400(
    client: TestClient,
    owner_headers: dict[str, str],
) -> None:
    prod_res = client.post(
        "/products",
        json={"sku": "HUGE_TOTAL_PROD", "name": "Expensive Item", "unit": "pcs", "price_paise": 100_000_000_000, "cost_paise": 1000},
        headers=owner_headers,
    )
    p_id = prod_res.json()["id"]
    client.post(
        "/stock/adjustments",
        json={"product_id": p_id, "qty_change": 20, "reason": "Stock"},
        headers=owner_headers,
    )

    res = client.post(
        "/sales",
        json={"payment_type": "cash", "items": [{"product_id": p_id, "qty": 11}]},
        headers=owner_headers,
    )
    assert res.status_code == 400
    assert res.json()["detail"] == "Sale total exceeds limit of 10^12 paise"

