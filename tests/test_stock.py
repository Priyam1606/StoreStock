import json
from fastapi.testclient import TestClient
from app.db import get_connection


def test_stock_equals_sum_of_movements(client: TestClient, owner_headers: dict[str, str], temp_db: str) -> None:
    prod_res = client.post(
        "/products",
        json={
            "sku": "STOCK_SUM_TEST",
            "name": "Stock Sum Item",
            "unit": "pcs",
            "price_paise": 1000,
            "cost_paise": 800,
            "reorder_level": 5,
        },
        headers=owner_headers,
    )
    prod_id = prod_res.json()["id"]

    conn = get_connection(temp_db)
    user_id = conn.execute("SELECT id FROM users WHERE role = 'owner'").fetchone()["id"]
    conn.execute(
        "INSERT INTO stock_movements (product_id, qty_change, kind, user_id, created_at) VALUES (?, 20, 'opening', ?, '2026-01-01T10:00:00Z')",
        (prod_id, user_id),
    )
    conn.execute(
        "INSERT INTO stock_movements (product_id, qty_change, kind, user_id, created_at) VALUES (?, 15, 'delivery', ?, '2026-01-01T11:00:00Z')",
        (prod_id, user_id),
    )
    conn.execute(
        "INSERT INTO stock_movements (product_id, qty_change, kind, user_id, created_at) VALUES (?, -5, 'sale', ?, '2026-01-01T12:00:00Z')",
        (prod_id, user_id),
    )
    conn.close()

    stock_res = client.get("/stock", headers=owner_headers)
    assert stock_res.status_code == 200
    items = stock_res.json()
    item = next(p for p in items if p["product_id"] == prod_id)
    assert item["current_stock"] == 30


def test_adjustment_success_and_audit_log(
    client: TestClient,
    owner_headers: dict[str, str],
    temp_db: str,
) -> None:
    prod_res = client.post(
        "/products",
        json={
            "sku": "ADJUST_PROD_1",
            "name": "Adjust Item",
            "unit": "pcs",
            "price_paise": 1000,
            "cost_paise": 800,
            "reorder_level": 5,
        },
        headers=owner_headers,
    )
    prod_id = prod_res.json()["id"]

    conn = get_connection(temp_db)
    user_id = conn.execute("SELECT id FROM users WHERE role = 'owner'").fetchone()["id"]
    conn.execute(
        "INSERT INTO stock_movements (product_id, qty_change, kind, user_id, created_at) VALUES (?, 10, 'opening', ?, '2026-01-01T10:00:00Z')",
        (prod_id, user_id),
    )
    conn.close()

    adj_res = client.post(
        "/stock/adjustments",
        json={
            "product_id": prod_id,
            "qty_change": 5,
            "reason": "Found uncounted stock on top shelf",
        },
        headers=owner_headers,
    )
    assert adj_res.status_code == 201
    data = adj_res.json()
    assert data["product_id"] == prod_id
    assert data["qty_change"] == 5
    assert data["current_stock"] == 15
    assert data["kind"] == "adjustment"

    conn = get_connection(temp_db)
    audit_row = conn.execute(
        "SELECT action, entity_type, entity_id, old_value, new_value FROM audit_log WHERE entity_type = 'stock' AND entity_id = ?",
        (prod_id,),
    ).fetchone()
    conn.close()

    assert audit_row is not None
    assert audit_row["action"] == "adjustment"
    assert json.loads(audit_row["old_value"]) == {"current_stock": 10}
    new_audit = json.loads(audit_row["new_value"])
    assert new_audit["current_stock"] == 15
    assert new_audit["qty_change"] == 5
    assert new_audit["reason"] == "Found uncounted stock on top shelf"


def test_adjustment_cannot_go_below_zero(client: TestClient, owner_headers: dict[str, str], temp_db: str) -> None:
    prod_res = client.post(
        "/products",
        json={
            "sku": "BELOW_ZERO_TEST",
            "name": "Zero Test Item",
            "unit": "pcs",
            "price_paise": 1000,
            "cost_paise": 800,
        },
        headers=owner_headers,
    )
    prod_id = prod_res.json()["id"]

    conn = get_connection(temp_db)
    user_id = conn.execute("SELECT id FROM users WHERE role = 'owner'").fetchone()["id"]
    conn.execute(
        "INSERT INTO stock_movements (product_id, qty_change, kind, user_id, created_at) VALUES (?, 10, 'opening', ?, '2026-01-01T10:00:00Z')",
        (prod_id, user_id),
    )
    conn.close()

    fail_res = client.post(
        "/stock/adjustments",
        json={
            "product_id": prod_id,
            "qty_change": -11,
            "reason": "Damage write-off",
        },
        headers=owner_headers,
    )
    assert fail_res.status_code == 409
    assert fail_res.json() == {"detail": "Adjustment would reduce stock below zero"}

    exact_res = client.post(
        "/stock/adjustments",
        json={
            "product_id": prod_id,
            "qty_change": -10,
            "reason": "Exact drain",
        },
        headers=owner_headers,
    )
    assert exact_res.status_code == 201
    assert exact_res.json()["current_stock"] == 0


def test_adjustment_zero_qty_change_rejected(client: TestClient, owner_headers: dict[str, str]) -> None:
    prod_res = client.post(
        "/products",
        json={
            "sku": "ZERO_ADJ_TEST",
            "name": "Zero Adj",
            "unit": "pcs",
            "price_paise": 1000,
            "cost_paise": 800,
        },
        headers=owner_headers,
    )
    prod_id = prod_res.json()["id"]

    res = client.post(
        "/stock/adjustments",
        json={
            "product_id": prod_id,
            "qty_change": 0,
            "reason": "Invalid zero adjustment",
        },
        headers=owner_headers,
    )
    assert res.status_code == 400
    assert res.json() == {"detail": "qty_change cannot be zero"}


def test_adjustment_empty_reason_rejected(client: TestClient, owner_headers: dict[str, str]) -> None:
    prod_res = client.post(
        "/products",
        json={
            "sku": "EMPTY_REASON_TEST",
            "name": "Empty Reason",
            "unit": "pcs",
            "price_paise": 1000,
            "cost_paise": 800,
        },
        headers=owner_headers,
    )
    prod_id = prod_res.json()["id"]

    res = client.post(
        "/stock/adjustments",
        json={
            "product_id": prod_id,
            "qty_change": 5,
            "reason": "   ",
        },
        headers=owner_headers,
    )
    assert res.status_code == 400
    assert res.json() == {"detail": "Reason is required"}


def test_staff_cannot_make_adjustment(client: TestClient, staff_headers: dict[str, str]) -> None:
    res = client.post(
        "/stock/adjustments",
        json={
            "product_id": 1,
            "qty_change": 5,
            "reason": "Staff attempt",
        },
        headers=staff_headers,
    )
    assert res.status_code == 403
    assert res.json() == {"detail": "Owner permission required"}


def test_low_stock_boundary(client: TestClient, owner_headers: dict[str, str], temp_db: str) -> None:
    above_res = client.post(
        "/products",
        json={
            "sku": "ABOVE_REORDER",
            "name": "Above Reorder",
            "unit": "pcs",
            "price_paise": 100,
            "cost_paise": 80,
            "reorder_level": 10,
        },
        headers=owner_headers,
    )
    above_id = above_res.json()["id"]

    equal_res = client.post(
        "/products",
        json={
            "sku": "EQUAL_REORDER",
            "name": "Equal Reorder",
            "unit": "pcs",
            "price_paise": 100,
            "cost_paise": 80,
            "reorder_level": 10,
        },
        headers=owner_headers,
    )
    equal_id = equal_res.json()["id"]

    below_res = client.post(
        "/products",
        json={
            "sku": "BELOW_REORDER",
            "name": "Below Reorder",
            "unit": "pcs",
            "price_paise": 100,
            "cost_paise": 80,
            "reorder_level": 10,
        },
        headers=owner_headers,
    )
    below_id = below_res.json()["id"]

    zero_res = client.post(
        "/products",
        json={
            "sku": "ZERO_REORDER_AND_STOCK",
            "name": "Zero Both",
            "unit": "pcs",
            "price_paise": 100,
            "cost_paise": 80,
            "reorder_level": 0,
        },
        headers=owner_headers,
    )
    zero_id = zero_res.json()["id"]

    conn = get_connection(temp_db)
    user_id = conn.execute("SELECT id FROM users WHERE role = 'owner'").fetchone()["id"]
    conn.execute(
        "INSERT INTO stock_movements (product_id, qty_change, kind, user_id, created_at) VALUES (?, 15, 'opening', ?, '2026-01-01T00:00:00Z')",
        (above_id, user_id),
    )
    conn.execute(
        "INSERT INTO stock_movements (product_id, qty_change, kind, user_id, created_at) VALUES (?, 10, 'opening', ?, '2026-01-01T00:00:00Z')",
        (equal_id, user_id),
    )
    conn.execute(
        "INSERT INTO stock_movements (product_id, qty_change, kind, user_id, created_at) VALUES (?, 5, 'opening', ?, '2026-01-01T00:00:00Z')",
        (below_id, user_id),
    )
    conn.close()

    low_res = client.get("/stock/low", headers=owner_headers)
    assert low_res.status_code == 200
    low_ids = [p["product_id"] for p in low_res.json()]

    assert above_id not in low_ids
    assert equal_id in low_ids
    assert below_id in low_ids
    assert zero_id in low_ids


def test_movement_history_newest_first_and_paginated(
    client: TestClient,
    owner_headers: dict[str, str],
    temp_db: str,
) -> None:
    prod_res = client.post(
        "/products",
        json={
            "sku": "HISTORY_PROD",
            "name": "History Item",
            "unit": "pcs",
            "price_paise": 100,
            "cost_paise": 80,
        },
        headers=owner_headers,
    )
    prod_id = prod_res.json()["id"]

    conn = get_connection(temp_db)
    user_id = conn.execute("SELECT id FROM users WHERE role = 'owner'").fetchone()["id"]
    conn.execute(
        "INSERT INTO stock_movements (product_id, qty_change, kind, user_id, note, created_at) VALUES (?, 10, 'opening', ?, 'First', '2026-01-01T10:00:00Z')",
        (prod_id, user_id),
    )
    conn.execute(
        "INSERT INTO stock_movements (product_id, qty_change, kind, user_id, note, created_at) VALUES (?, 5, 'delivery', ?, 'Second', '2026-01-01T11:00:00Z')",
        (prod_id, user_id),
    )
    conn.execute(
        "INSERT INTO stock_movements (product_id, qty_change, kind, user_id, note, created_at) VALUES (?, -2, 'sale', ?, 'Third', '2026-01-01T12:00:00Z')",
        (prod_id, user_id),
    )
    conn.close()

    first_page = client.get(f"/products/{prod_id}/movements?limit=2&offset=0", headers=owner_headers)
    assert first_page.status_code == 200
    data1 = first_page.json()
    assert len(data1) == 2
    assert data1[0]["note"] == "Third"
    assert data1[1]["note"] == "Second"

    second_page = client.get(f"/products/{prod_id}/movements?limit=2&offset=2", headers=owner_headers)
    assert second_page.status_code == 200
    data2 = second_page.json()
    assert len(data2) == 1
    assert data2[0]["note"] == "First"


def test_staff_can_view_stock_and_movements(
    client: TestClient,
    owner_headers: dict[str, str],
    staff_headers: dict[str, str],
) -> None:
    prod_res = client.post(
        "/products",
        json={
            "sku": "STAFF_VIEW_STOCK",
            "name": "Staff View Item",
            "unit": "pcs",
            "price_paise": 100,
            "cost_paise": 80,
        },
        headers=owner_headers,
    )
    prod_id = prod_res.json()["id"]

    stock_res = client.get("/stock", headers=staff_headers)
    assert stock_res.status_code == 200

    low_res = client.get("/stock/low", headers=staff_headers)
    assert low_res.status_code == 200

    movements_res = client.get(f"/products/{prod_id}/movements", headers=staff_headers)
    assert movements_res.status_code == 200


def test_stock_movements_nonexistent_product(client: TestClient, owner_headers: dict[str, str]) -> None:
    res = client.get("/products/999999/movements", headers=owner_headers)
    assert res.status_code == 404
    assert res.json() == {"detail": "Product not found"}


def test_stock_adjustment_nonexistent_product(client: TestClient, owner_headers: dict[str, str]) -> None:
    res = client.post(
        "/stock/adjustments",
        json={
            "product_id": 999999,
            "qty_change": 5,
            "reason": "Nonexistent",
        },
        headers=owner_headers,
    )
    assert res.status_code == 404
    assert res.json() == {"detail": "Product not found"}
