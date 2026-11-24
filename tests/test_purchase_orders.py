from fastapi.testclient import TestClient
from app.db import get_connection


def create_test_product(
    client: TestClient,
    headers: dict[str, str],
    sku: str = "PO_PROD_1",
    name: str = "PO Product",
    reorder_level: int = 10,
    cost_paise: int = 500,
    price_paise: int = 1000,
) -> int:
    res = client.post(
        "/products",
        json={
            "sku": sku,
            "name": name,
            "unit": "pcs",
            "price_paise": price_paise,
            "cost_paise": cost_paise,
            "reorder_level": reorder_level,
        },
        headers=headers,
    )
    return int(res.json()["id"])


def test_supplier_crud_and_permissions(
    client: TestClient,
    owner_headers: dict[str, str],
    staff_headers: dict[str, str],
) -> None:
    create_res = client.post(
        "/suppliers",
        json={"name": "Acme Supplies", "phone": "9876543210"},
        headers=owner_headers,
    )
    assert create_res.status_code == 201
    sup_id = create_res.json()["id"]
    assert create_res.json()["name"] == "Acme Supplies"
    assert create_res.json()["phone"] == "9876543210"
    assert create_res.json()["active"] is True

    staff_create = client.post(
        "/suppliers",
        json={"name": "Unauthorized Supplier"},
        headers=staff_headers,
    )
    assert staff_create.status_code == 403

    empty_name = client.post(
        "/suppliers",
        json={"name": "   "},
        headers=owner_headers,
    )
    assert empty_name.status_code == 400

    get_res = client.get(f"/suppliers/{sup_id}", headers=staff_headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == sup_id

    not_found = client.get("/suppliers/999999", headers=owner_headers)
    assert not_found.status_code == 404

    patch_staff = client.patch(
        f"/suppliers/{sup_id}",
        json={"name": "Staff Update"},
        headers=staff_headers,
    )
    assert patch_staff.status_code == 403

    patch_owner = client.patch(
        f"/suppliers/{sup_id}",
        json={"name": "Acme Global", "active": False},
        headers=owner_headers,
    )
    assert patch_owner.status_code == 200
    assert patch_owner.json()["name"] == "Acme Global"
    assert patch_owner.json()["active"] is False


def test_create_purchase_order_validation(
    client: TestClient,
    owner_headers: dict[str, str],
    staff_headers: dict[str, str],
) -> None:
    sup_res = client.post(
        "/suppliers",
        json={"name": "PO Supplier 1"},
        headers=owner_headers,
    )
    sup_id = sup_res.json()["id"]

    p_id = create_test_product(client, owner_headers, sku="PO_VAL_1")

    staff_po = client.post(
        "/purchase-orders",
        json={"supplier_id": sup_id, "items": [{"product_id": p_id, "qty_ordered": 50, "unit_cost_paise": 400}]},
        headers=staff_headers,
    )
    assert staff_po.status_code == 403

    dup_po = client.post(
        "/purchase-orders",
        json={
            "supplier_id": sup_id,
            "items": [
                {"product_id": p_id, "qty_ordered": 10, "unit_cost_paise": 400},
                {"product_id": p_id, "qty_ordered": 20, "unit_cost_paise": 400},
            ],
        },
        headers=owner_headers,
    )
    assert dup_po.status_code == 400
    assert dup_po.json()["detail"] == "Duplicate product lines in purchase order"

    missing_sup = client.post(
        "/purchase-orders",
        json={"supplier_id": 999999, "items": [{"product_id": p_id, "qty_ordered": 10, "unit_cost_paise": 400}]},
        headers=owner_headers,
    )
    assert missing_sup.status_code == 404

    client.patch(f"/suppliers/{sup_id}", json={"active": False}, headers=owner_headers)
    inactive_sup = client.post(
        "/purchase-orders",
        json={"supplier_id": sup_id, "items": [{"product_id": p_id, "qty_ordered": 10, "unit_cost_paise": 400}]},
        headers=owner_headers,
    )
    assert inactive_sup.status_code == 400
    assert inactive_sup.json()["detail"] == "Supplier is inactive"

    client.patch(f"/suppliers/{sup_id}", json={"active": True}, headers=owner_headers)
    missing_prod = client.post(
        "/purchase-orders",
        json={"supplier_id": sup_id, "items": [{"product_id": 999999, "qty_ordered": 10, "unit_cost_paise": 400}]},
        headers=owner_headers,
    )
    assert missing_prod.status_code == 404

    valid_po = client.post(
        "/purchase-orders",
        json={"supplier_id": sup_id, "items": [{"product_id": p_id, "qty_ordered": 100, "unit_cost_paise": 450}]},
        headers=owner_headers,
    )
    assert valid_po.status_code == 201
    data = valid_po.json()
    assert data["status"] == "draft"
    assert data["supplier_id"] == sup_id
    assert len(data["items"]) == 1
    assert data["items"][0]["qty_ordered"] == 100
    assert data["items"][0]["qty_received"] == 0
    assert data["items"][0]["unit_cost_paise"] == 450


def test_purchase_order_state_transitions(
    client: TestClient,
    owner_headers: dict[str, str],
) -> None:
    sup_res = client.post("/suppliers", json={"name": "State Sup"}, headers=owner_headers)
    sup_id = sup_res.json()["id"]
    p_id = create_test_product(client, owner_headers, sku="PO_STATE_1")

    po = client.post(
        "/purchase-orders",
        json={"supplier_id": sup_id, "items": [{"product_id": p_id, "qty_ordered": 10, "unit_cost_paise": 100}]},
        headers=owner_headers,
    ).json()
    po_id = po["id"]

    rec_draft = client.post(
        f"/purchase-orders/{po_id}/receive",
        json={"items": [{"product_id": p_id, "qty": 5}]},
        headers=owner_headers,
    )
    assert rec_draft.status_code == 409
    assert "Cannot receive goods" in rec_draft.json()["detail"]

    send_res = client.post(f"/purchase-orders/{po_id}/send", headers=owner_headers)
    assert send_res.status_code == 200
    assert send_res.json()["status"] == "sent"
    assert send_res.json()["sent_at"] is not None

    send_again = client.post(f"/purchase-orders/{po_id}/send", headers=owner_headers)
    assert send_again.status_code == 409

    cancel_res = client.post(f"/purchase-orders/{po_id}/cancel", headers=owner_headers)
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "cancelled"

    cancel_again = client.post(f"/purchase-orders/{po_id}/cancel", headers=owner_headers)
    assert cancel_again.status_code == 409

    rec_cancelled = client.post(
        f"/purchase-orders/{po_id}/receive",
        json={"items": [{"product_id": p_id, "qty": 5}]},
        headers=owner_headers,
    )
    assert rec_cancelled.status_code == 409


def test_receive_purchase_order_partial_and_full(
    client: TestClient,
    owner_headers: dict[str, str],
    staff_headers: dict[str, str],
    temp_db: str,
) -> None:
    sup_res = client.post("/suppliers", json={"name": "Receive Sup"}, headers=owner_headers)
    sup_id = sup_res.json()["id"]
    p1 = create_test_product(client, owner_headers, sku="PO_REC_1")
    p2 = create_test_product(client, owner_headers, sku="PO_REC_2")

    po = client.post(
        "/purchase-orders",
        json={
            "supplier_id": sup_id,
            "items": [
                {"product_id": p1, "qty_ordered": 20, "unit_cost_paise": 200},
                {"product_id": p2, "qty_ordered": 30, "unit_cost_paise": 300},
            ],
        },
        headers=owner_headers,
    ).json()
    po_id = po["id"]

    client.post(f"/purchase-orders/{po_id}/send", headers=owner_headers)

    over_receive = client.post(
        f"/purchase-orders/{po_id}/receive",
        json={"items": [{"product_id": p1, "qty": 25}]},
        headers=staff_headers,
    )
    assert over_receive.status_code == 409
    assert "Received quantity exceeds ordered quantity" in over_receive.json()["detail"]

    part_res = client.post(
        f"/purchase-orders/{po_id}/receive",
        json={"items": [{"product_id": p1, "qty": 10}, {"product_id": p2, "qty": 15}]},
        headers=staff_headers,
    )
    assert part_res.status_code == 200
    part_data = part_res.json()
    assert part_data["status"] == "partially_received"
    assert part_data["received_at"] is None

    conn = get_connection(temp_db)
    s1 = conn.execute("SELECT COALESCE(SUM(qty_change), 0) AS s FROM stock_movements WHERE product_id = ?", (p1,)).fetchone()["s"]
    s2 = conn.execute("SELECT COALESCE(SUM(qty_change), 0) AS s FROM stock_movements WHERE product_id = ?", (p2,)).fetchone()["s"]
    mv1 = conn.execute(
        "SELECT kind, ref_type, ref_id, qty_change FROM stock_movements WHERE product_id = ? ORDER BY id DESC LIMIT 1",
        (p1,),
    ).fetchone()
    conn.close()
    assert s1 == 10
    assert s2 == 15
    assert mv1["kind"] == "delivery"
    assert mv1["ref_type"] == "purchase_order"
    assert mv1["ref_id"] == po_id
    assert mv1["qty_change"] == 10

    full_res = client.post(
        f"/purchase-orders/{po_id}/receive",
        json={"items": [{"product_id": p1, "qty": 10}, {"product_id": p2, "qty": 15}]},
        headers=owner_headers,
    )
    assert full_res.status_code == 200
    full_data = full_res.json()
    assert full_data["status"] == "received"
    assert full_data["received_at"] is not None

    after_full = client.post(
        f"/purchase-orders/{po_id}/receive",
        json={"items": [{"product_id": p1, "qty": 1}]},
        headers=owner_headers,
    )
    assert after_full.status_code == 409


def test_purchase_order_suggestions(
    client: TestClient,
    owner_headers: dict[str, str],
    staff_headers: dict[str, str],
) -> None:
    p1 = create_test_product(client, owner_headers, sku="SUGG_P1", reorder_level=10)
    p2 = create_test_product(client, owner_headers, sku="SUGG_P2", reorder_level=5)
    p3 = create_test_product(client, owner_headers, sku="SUGG_P3", reorder_level=8)

    client.post(
        "/stock/adjustments",
        json={"product_id": p1, "qty_change": 4, "reason": "Stock"},
        headers=owner_headers,
    )

    client.post(
        "/stock/adjustments",
        json={"product_id": p3, "qty_change": 15, "reason": "Stock"},
        headers=owner_headers,
    )

    staff_sugg = client.post("/purchase-orders/suggest", headers=staff_headers)
    assert staff_sugg.status_code == 200
    staff_items = staff_sugg.json()
    assert len(staff_items) > 0
    assert "unit_cost_paise" not in staff_items[0]

    sugg_res = client.post("/purchase-orders/suggest", headers=owner_headers)
    assert sugg_res.status_code == 200
    assert "unit_cost_paise" in sugg_res.json()[0]
    suggestions = {s["product_id"]: s for s in sugg_res.json()}

    assert p1 in suggestions
    assert suggestions[p1]["current_stock"] == 4
    assert suggestions[p1]["suggested_qty"] == 16

    assert p2 in suggestions
    assert suggestions[p2]["current_stock"] == 0
    assert suggestions[p2]["suggested_qty"] == 10

    assert p3 not in suggestions


def test_staff_never_sees_po_unit_cost(
    client: TestClient,
    owner_headers: dict[str, str],
    staff_headers: dict[str, str],
) -> None:
    sup_res = client.post("/suppliers", json={"name": "Cost Sup"}, headers=owner_headers)
    sup_id = sup_res.json()["id"]
    p_id = create_test_product(client, owner_headers, sku="STAFF_NO_COST_PO")

    po_res = client.post(
        "/purchase-orders",
        json={"supplier_id": sup_id, "items": [{"product_id": p_id, "qty_ordered": 50, "unit_cost_paise": 750}]},
        headers=owner_headers,
    )
    po_id = po_res.json()["id"]

    owner_get = client.get(f"/purchase-orders/{po_id}", headers=owner_headers)
    assert owner_get.status_code == 200
    assert owner_get.json()["items"][0]["unit_cost_paise"] == 750

    staff_get = client.get(f"/purchase-orders/{po_id}", headers=staff_headers)
    assert staff_get.status_code == 200
    assert "unit_cost_paise" not in staff_get.json()["items"][0]

    owner_list = client.get(f"/purchase-orders?supplier_id={sup_id}", headers=owner_headers)
    assert owner_list.status_code == 200
    assert owner_list.json()[0]["items"][0]["unit_cost_paise"] == 750

    staff_list = client.get(f"/purchase-orders?supplier_id={sup_id}", headers=staff_headers)
    assert staff_list.status_code == 200
    assert "unit_cost_paise" not in staff_list.json()[0]["items"][0]


def test_receive_rejects_foreign_item_id_and_zero_or_negative_qty(
    client: TestClient,
    owner_headers: dict[str, str],
) -> None:
    sup_res = client.post("/suppliers", json={"name": "Reject Sup"}, headers=owner_headers)
    sup_id = sup_res.json()["id"]
    p1 = create_test_product(client, owner_headers, sku="REJ_P1")
    p2 = create_test_product(client, owner_headers, sku="REJ_P2")

    po1 = client.post(
        "/purchase-orders",
        json={"supplier_id": sup_id, "items": [{"product_id": p1, "qty_ordered": 20, "unit_cost_paise": 100}]},
        headers=owner_headers,
    ).json()
    po2 = client.post(
        "/purchase-orders",
        json={"supplier_id": sup_id, "items": [{"product_id": p2, "qty_ordered": 20, "unit_cost_paise": 100}]},
        headers=owner_headers,
    ).json()

    client.post(f"/purchase-orders/{po1['id']}/send", headers=owner_headers)
    client.post(f"/purchase-orders/{po2['id']}/send", headers=owner_headers)

    po1_item_id = po1["items"][0]["id"]
    po2_item_id = po2["items"][0]["id"]

    foreign_item = client.post(
        f"/purchase-orders/{po1['id']}/receive",
        json={"items": [{"item_id": po2_item_id, "qty": 5}]},
        headers=owner_headers,
    )
    assert foreign_item.status_code == 400
    assert "does not belong to this purchase order" in foreign_item.json()["detail"]

    missing_item = client.post(
        f"/purchase-orders/{po1['id']}/receive",
        json={"items": [{"item_id": 999999, "qty": 5}]},
        headers=owner_headers,
    )
    assert missing_item.status_code == 400
    assert "does not belong to this purchase order" in missing_item.json()["detail"]

    zero_qty = client.post(
        f"/purchase-orders/{po1['id']}/receive",
        json={"items": [{"item_id": po1_item_id, "qty": 0}]},
        headers=owner_headers,
    )
    assert zero_qty.status_code == 400
    assert "Received quantity must be greater than zero" in zero_qty.json()["detail"]

    negative_qty = client.post(
        f"/purchase-orders/{po1['id']}/receive",
        json={"items": [{"item_id": po1_item_id, "qty": -5}]},
        headers=owner_headers,
    )
    assert negative_qty.status_code == 400
    assert "Received quantity must be greater than zero" in negative_qty.json()["detail"]

