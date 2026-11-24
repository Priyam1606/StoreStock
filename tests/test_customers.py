from fastapi.testclient import TestClient
from app.db import get_connection


def test_create_customer_success_and_duplicate_phone(
    client: TestClient,
    owner_headers: dict[str, str],
) -> None:
    res = client.post(
        "/customers",
        json={"name": "Ramesh Kumar", "phone": "9876543210", "credit_limit_paise": 25000},
        headers=owner_headers,
    )
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Ramesh Kumar"
    assert data["phone"] == "9876543210"
    assert data["credit_limit_paise"] == 25000
    assert data["active"] is True
    assert "id" in data

    dup_res = client.post(
        "/customers",
        json={"name": "Another Person", "phone": "9876543210", "credit_limit_paise": 10000},
        headers=owner_headers,
    )
    assert dup_res.status_code == 409
    assert dup_res.json() == {"detail": "Phone number already registered to another customer"}


def test_staff_can_create_customer(client: TestClient, staff_headers: dict[str, str]) -> None:
    res = client.post(
        "/customers",
        json={"name": "Suresh Raina", "phone": "9876500001", "credit_limit_paise": 0},
        headers=staff_headers,
    )
    assert res.status_code == 201
    assert res.json()["name"] == "Suresh Raina"


def test_get_customer_by_id_and_not_found(client: TestClient, owner_headers: dict[str, str]) -> None:
    create_res = client.post(
        "/customers",
        json={"name": "Pooja Sharma", "credit_limit_paise": 5000},
        headers=owner_headers,
    )
    cust_id = create_res.json()["id"]

    get_res = client.get(f"/customers/{cust_id}", headers=owner_headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == cust_id
    assert get_res.json()["name"] == "Pooja Sharma"

    not_found_res = client.get("/customers/999999", headers=owner_headers)
    assert not_found_res.status_code == 404
    assert not_found_res.json() == {"detail": "Customer not found"}


def test_search_customers_by_name_and_phone(client: TestClient, owner_headers: dict[str, str]) -> None:
    client.post(
        "/customers",
        json={"name": "Amitabh Bachchan", "phone": "9998887771"},
        headers=owner_headers,
    )
    client.post(
        "/customers",
        json={"name": "Abhishek Bachchan", "phone": "9998887772"},
        headers=owner_headers,
    )

    search_name = client.get("/customers?q=amitabh", headers=owner_headers)
    assert search_name.status_code == 200
    results1 = search_name.json()
    assert len(results1) == 1
    assert results1[0]["name"] == "Amitabh Bachchan"

    search_phone = client.get("/customers?q=7772", headers=owner_headers)
    assert search_phone.status_code == 200
    results2 = search_phone.json()
    assert len(results2) == 1
    assert results2[0]["name"] == "Abhishek Bachchan"


def test_patch_customer_permissions(
    client: TestClient,
    owner_headers: dict[str, str],
    staff_headers: dict[str, str],
) -> None:
    create_res = client.post(
        "/customers",
        json={"name": "Vikram Seth", "phone": "9123456789", "credit_limit_paise": 5000},
        headers=owner_headers,
    )
    cust_id = create_res.json()["id"]

    staff_fail_limit = client.patch(
        f"/customers/{cust_id}",
        json={"credit_limit_paise": 10000},
        headers=staff_headers,
    )
    assert staff_fail_limit.status_code == 403
    assert staff_fail_limit.json() == {"detail": "Owner permission required to update credit limit or active status"}

    staff_fail_active = client.patch(
        f"/customers/{cust_id}",
        json={"active": False},
        headers=staff_headers,
    )
    assert staff_fail_active.status_code == 403

    staff_success_name = client.patch(
        f"/customers/{cust_id}",
        json={"name": "Vikram Seth Updated"},
        headers=staff_headers,
    )
    assert staff_success_name.status_code == 200
    assert staff_success_name.json()["name"] == "Vikram Seth Updated"

    owner_success_limit = client.patch(
        f"/customers/{cust_id}",
        json={"credit_limit_paise": 15000, "active": False},
        headers=owner_headers,
    )
    assert owner_success_limit.status_code == 200
    assert owner_success_limit.json()["credit_limit_paise"] == 15000
    assert owner_success_limit.json()["active"] is False


def test_customer_balance_equals_sum_of_entries(
    client: TestClient,
    owner_headers: dict[str, str],
    temp_db: str,
) -> None:
    cust = client.post(
        "/customers",
        json={"name": "Ledger Customer", "credit_limit_paise": 50000},
        headers=owner_headers,
    ).json()
    cust_id = cust["id"]

    p = client.post(
        "/products",
        json={"sku": "BALANCE_PROD", "name": "Item", "unit": "pcs", "price_paise": 1000, "cost_paise": 800},
        headers=owner_headers,
    ).json()
    p_id = p["id"]
    client.post("/stock/adjustments", json={"product_id": p_id, "qty_change": 20, "reason": "S"}, headers=owner_headers)

    s1 = client.post(
        "/sales",
        json={"payment_type": "credit", "customer_id": cust_id, "items": [{"product_id": p_id, "qty": 3}]},
        headers=owner_headers,
    ).json()

    s2 = client.post(
        "/sales",
        json={"payment_type": "credit", "customer_id": cust_id, "items": [{"product_id": p_id, "qty": 2}]},
        headers=owner_headers,
    ).json()

    bal_res1 = client.get(f"/customers/{cust_id}/balance", headers=owner_headers)
    assert bal_res1.status_code == 200
    assert bal_res1.json()["balance_paise"] == 5000

    pay_res = client.post(
        f"/customers/{cust_id}/payments",
        json={"amount_paise": 2000, "note": "Partial payment"},
        headers=owner_headers,
    )
    assert pay_res.status_code == 201

    bal_res2 = client.get(f"/customers/{cust_id}/balance", headers=owner_headers)
    assert bal_res2.json()["balance_paise"] == 3000

    ret_res = client.post(
        f"/sales/{s1['id']}/returns",
        json={"items": [{"sale_item_id": s1["items"][0]["id"], "qty": 1}]},
        headers=owner_headers,
    )
    assert ret_res.status_code == 201

    bal_res3 = client.get(f"/customers/{cust_id}/balance", headers=owner_headers)
    assert bal_res3.json()["balance_paise"] == 2000


def test_overpayment_rejected_with_409(
    client: TestClient,
    owner_headers: dict[str, str],
) -> None:
    cust = client.post(
        "/customers",
        json={"name": "Overpay Customer", "credit_limit_paise": 10000},
        headers=owner_headers,
    ).json()
    cust_id = cust["id"]

    p = client.post(
        "/products",
        json={"sku": "OVERPAY_PROD", "name": "Item", "unit": "pcs", "price_paise": 1500, "cost_paise": 1000},
        headers=owner_headers,
    ).json()
    client.post("/stock/adjustments", json={"product_id": p["id"], "qty_change": 5, "reason": "S"}, headers=owner_headers)

    client.post(
        "/sales",
        json={"payment_type": "credit", "customer_id": cust_id, "items": [{"product_id": p["id"], "qty": 1}]},
        headers=owner_headers,
    )

    over_res = client.post(
        f"/customers/{cust_id}/payments",
        json={"amount_paise": 1501, "note": "Too much"},
        headers=owner_headers,
    )
    assert over_res.status_code == 409
    assert over_res.json() == {"detail": "Payment exceeds current balance"}

    exact_res = client.post(
        f"/customers/{cust_id}/payments",
        json={"amount_paise": 1500, "note": "Exact payoff"},
        headers=owner_headers,
    )
    assert exact_res.status_code == 201

    final_bal = client.get(f"/customers/{cust_id}/balance", headers=owner_headers)
    assert final_bal.json()["balance_paise"] == 0


def test_payment_on_inactive_customer_rejected_409(
    client: TestClient,
    owner_headers: dict[str, str],
) -> None:
    cust = client.post(
        "/customers",
        json={"name": "Inactive Pay Customer", "credit_limit_paise": 10000},
        headers=owner_headers,
    ).json()
    cust_id = cust["id"]

    p = client.post(
        "/products",
        json={"sku": "INACT_PAY_PROD", "name": "Item", "unit": "pcs", "price_paise": 1000, "cost_paise": 800},
        headers=owner_headers,
    ).json()
    client.post("/stock/adjustments", json={"product_id": p["id"], "qty_change": 5, "reason": "S"}, headers=owner_headers)

    client.post(
        "/sales",
        json={"payment_type": "credit", "customer_id": cust_id, "items": [{"product_id": p["id"], "qty": 1}]},
        headers=owner_headers,
    )

    client.patch(f"/customers/{cust_id}", json={"active": False}, headers=owner_headers)

    pay_res = client.post(
        f"/customers/{cust_id}/payments",
        json={"amount_paise": 500},
        headers=owner_headers,
    )
    assert pay_res.status_code == 409
    assert pay_res.json() == {"detail": "Customer is inactive"}


def test_customer_ledger_pagination_and_order(
    client: TestClient,
    owner_headers: dict[str, str],
    temp_db: str,
) -> None:
    cust = client.post(
        "/customers",
        json={"name": "Ledger Order Customer", "credit_limit_paise": 20000},
        headers=owner_headers,
    ).json()
    cust_id = cust["id"]

    conn = get_connection(temp_db)
    conn.execute(
        "INSERT INTO credit_entries (customer_id, kind, amount_paise, user_id, note, created_at) VALUES (?, 'credit_sale', 1000, 1, 'First', '2026-01-01T10:00:00Z')",
        (cust_id,),
    )
    conn.execute(
        "INSERT INTO credit_entries (customer_id, kind, amount_paise, user_id, note, created_at) VALUES (?, 'credit_sale', 2000, 1, 'Second', '2026-01-01T11:00:00Z')",
        (cust_id,),
    )
    conn.execute(
        "INSERT INTO credit_entries (customer_id, kind, amount_paise, user_id, note, created_at) VALUES (?, 'payment', -500, 1, 'Third', '2026-01-01T12:00:00Z')",
        (cust_id,),
    )
    conn.close()

    p1 = client.get(f"/customers/{cust_id}/ledger?limit=2&offset=0", headers=owner_headers)
    assert p1.status_code == 200
    d1 = p1.json()
    assert len(d1) == 2
    assert d1[0]["note"] == "Third"
    assert d1[1]["note"] == "Second"

    p2 = client.get(f"/customers/{cust_id}/ledger?limit=2&offset=2", headers=owner_headers)
    assert p2.status_code == 200
    d2 = p2.json()
    assert len(d2) == 1
    assert d2[0]["note"] == "First"
