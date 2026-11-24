from fastapi.testclient import TestClient


def create_product(
    client: TestClient,
    headers: dict[str, str],
    sku: str,
    name: str,
    price_paise: int,
    cost_paise: int,
    stock: int = 0,
) -> int:
    res = client.post(
        "/products",
        json={
            "sku": sku,
            "name": name,
            "unit": "pcs",
            "price_paise": price_paise,
            "cost_paise": cost_paise,
            "reorder_level": 5,
        },
        headers=headers,
    )
    p_id = int(res.json()["id"])
    if stock > 0:
        client.post(
            "/stock/adjustments",
            json={"product_id": p_id, "qty_change": stock, "reason": "Initial"},
            headers=headers,
        )
    return p_id


def test_reports_permission_staff_forbidden(
    client: TestClient,
    staff_headers: dict[str, str],
) -> None:
    assert client.get("/reports/daily-summary", headers=staff_headers).status_code == 403
    assert client.get("/reports/top-selling", headers=staff_headers).status_code == 403
    assert client.get("/reports/credit-summary", headers=staff_headers).status_code == 403
    assert client.get("/reports/inventory-valuation", headers=staff_headers).status_code == 403


def test_daily_summary_empty_day(
    client: TestClient,
    owner_headers: dict[str, str],
) -> None:
    res = client.get("/reports/daily-summary?date=2026-01-01", headers=owner_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["date"] == "2026-01-01"
    assert data["total_sales_paise"] == 0
    assert data["total_cash_sales_paise"] == 0
    assert data["total_credit_sales_paise"] == 0
    assert data["total_returns_paise"] == 0
    assert data["net_sales_paise"] == 0
    assert data["total_cost_paise"] == 0
    assert data["gross_profit_paise"] == 0
    assert data["sales_count"] == 0
    assert data["returns_count"] == 0


def test_daily_summary_invalid_date(
    client: TestClient,
    owner_headers: dict[str, str],
) -> None:
    res = client.get("/reports/daily-summary?date=invalid-date", headers=owner_headers)
    assert res.status_code == 400


def test_daily_summary_with_sales_and_returns(
    client: TestClient,
    owner_headers: dict[str, str],
) -> None:
    p1 = create_product(client, owner_headers, sku="REP_P1", name="Item 1", price_paise=1000, cost_paise=600, stock=50)
    p2 = create_product(client, owner_headers, sku="REP_P2", name="Item 2", price_paise=2000, cost_paise=1200, stock=50)

    cust_res = client.post(
        "/customers",
        json={"name": "Report Customer", "credit_limit_paise": 100000},
        headers=owner_headers,
    )
    cust_id = cust_res.json()["id"]

    sale1_res = client.post(
        "/sales",
        json={
            "payment_type": "cash",
            "items": [
                {"product_id": p1, "qty": 5},
                {"product_id": p2, "qty": 2},
            ],
        },
        headers=owner_headers,
    )
    assert sale1_res.status_code == 201

    sale2_res = client.post(
        "/sales",
        json={
            "payment_type": "credit",
            "customer_id": cust_id,
            "items": [{"product_id": p1, "qty": 3}],
        },
        headers=owner_headers,
    )
    assert sale2_res.status_code == 201
    sale2_id = sale2_res.json()["id"]
    sale2_item_id = sale2_res.json()["items"][0]["id"]

    ret_res = client.post(
        f"/sales/{sale2_id}/returns",
        json={"items": [{"sale_item_id": sale2_item_id, "qty": 1}]},
        headers=owner_headers,
    )
    assert ret_res.status_code == 201

    rep_res = client.get("/reports/daily-summary", headers=owner_headers)
    assert rep_res.status_code == 200
    data = rep_res.json()

    assert data["total_sales_paise"] == 12000
    assert data["total_cash_sales_paise"] == 9000
    assert data["total_credit_sales_paise"] == 3000
    assert data["total_returns_paise"] == 1000
    assert data["net_sales_paise"] == 11000
    assert data["total_cost_paise"] == 6600
    assert data["gross_profit_paise"] == 4400
    assert data["sales_count"] == 2
    assert data["returns_count"] == 1


def test_top_selling_report(
    client: TestClient,
    owner_headers: dict[str, str],
) -> None:
    p1 = create_product(client, owner_headers, sku="TOP_P1", name="Product Top 1", price_paise=100, cost_paise=50, stock=100)
    p2 = create_product(client, owner_headers, sku="TOP_P2", name="Product Top 2", price_paise=500, cost_paise=300, stock=100)

    client.post(
        "/sales",
        json={"payment_type": "cash", "items": [{"product_id": p1, "qty": 20}, {"product_id": p2, "qty": 5}]},
        headers=owner_headers,
    )

    res = client.get("/reports/top-selling?limit=5", headers=owner_headers)
    assert res.status_code == 200
    items = res.json()
    assert len(items) >= 2
    assert items[0]["product_id"] == p1
    assert items[0]["qty_sold"] == 20
    assert items[0]["total_revenue_paise"] == 2000


def test_credit_summary_report(
    client: TestClient,
    owner_headers: dict[str, str],
) -> None:
    c1 = client.post("/customers", json={"name": "Cred Cust 1", "credit_limit_paise": 50000}, headers=owner_headers).json()["id"]
    c2 = client.post("/customers", json={"name": "Cred Cust 2", "credit_limit_paise": 80000}, headers=owner_headers).json()["id"]

    p = create_product(client, owner_headers, sku="CRED_PROD", name="Cred Prod", price_paise=1000, cost_paise=500, stock=50)

    client.post(
        "/sales",
        json={"payment_type": "credit", "customer_id": c1, "items": [{"product_id": p, "qty": 10}]},
        headers=owner_headers,
    )
    client.post(
        "/customers/{c1}/payments".format(c1=c1),
        json={"amount_paise": 2000, "note": "Part pay"},
        headers=owner_headers,
    )

    client.post(
        "/sales",
        json={"payment_type": "credit", "customer_id": c2, "items": [{"product_id": p, "qty": 15}]},
        headers=owner_headers,
    )

    res = client.get("/reports/credit-summary", headers=owner_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_outstanding_paise"] == 23000
    assert data["customers_with_balance_count"] >= 2


def test_inventory_valuation_report(
    client: TestClient,
    owner_headers: dict[str, str],
) -> None:
    p1 = create_product(client, owner_headers, sku="VAL_P1", name="Val Prod 1", price_paise=1000, cost_paise=600, stock=10)
    p2 = create_product(client, owner_headers, sku="VAL_P2", name="Val Prod 2", price_paise=2000, cost_paise=1400, stock=5)

    res = client.get("/reports/inventory-valuation", headers=owner_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_items"] >= 15
    assert data["total_cost_paise"] >= 13000
    assert data["total_retail_paise"] >= 20000
    assert data["potential_profit_paise"] == data["total_retail_paise"] - data["total_cost_paise"]


def test_product_cost_change_does_not_alter_past_sales_gross_profit(
    client: TestClient,
    owner_headers: dict[str, str],
) -> None:
    p = create_product(client, owner_headers, sku="COST_CHG_P", name="Cost Chg Item", price_paise=1000, cost_paise=600, stock=10)

    client.post(
        "/sales",
        json={"payment_type": "cash", "items": [{"product_id": p, "qty": 2}]},
        headers=owner_headers,
    )

    r1 = client.get("/reports/daily-summary", headers=owner_headers).json()
    assert r1["total_sales_paise"] >= 2000
    profit_before = r1["gross_profit_paise"]
    cost_before = r1["total_cost_paise"]

    client.patch(
        f"/products/{p}",
        json={"cost_paise": 950},
        headers=owner_headers,
    )

    r2 = client.get("/reports/daily-summary", headers=owner_headers).json()
    assert r2["total_cost_paise"] == cost_before
    assert r2["gross_profit_paise"] == profit_before


def test_returns_count_on_return_date_not_sale_date(
    client: TestClient,
    owner_headers: dict[str, str],
    temp_db: str,
) -> None:
    from app.db import get_connection

    p = create_product(client, owner_headers, sku="RET_DATE_P", name="Ret Date Item", price_paise=1000, cost_paise=500, stock=10)

    conn = get_connection(temp_db)
    u_id = conn.execute("SELECT id FROM users WHERE role = 'owner'").fetchone()["id"]

    cur_s = conn.execute(
        "INSERT INTO sales (customer_id, user_id, payment_type, total_paise, created_at) VALUES (NULL, ?, 'cash', 1000, '2026-06-10T10:00:00+00:00')",
        (u_id,),
    )
    s_id = int(cur_s.lastrowid)

    cur_si = conn.execute(
        "INSERT INTO sale_items (sale_id, product_id, qty, unit_price_paise, unit_cost_paise, line_total_paise) VALUES (?, ?, 1, 1000, 500, 1000)",
        (s_id, p),
    )
    si_id = int(cur_si.lastrowid)

    cur_r = conn.execute(
        "INSERT INTO returns (sale_id, user_id, refund_paise, created_at) VALUES (?, ?, 1000, '2026-06-11T10:00:00+00:00')",
        (s_id, u_id),
    )
    r_id = int(cur_r.lastrowid)

    conn.execute(
        "INSERT INTO return_items (return_id, sale_item_id, qty) VALUES (?, ?, 1)",
        (r_id, si_id),
    )
    conn.close()

    rep_day1 = client.get("/reports/daily-summary?date=2026-06-10", headers=owner_headers).json()
    assert rep_day1["sales_count"] == 1
    assert rep_day1["returns_count"] == 0
    assert rep_day1["total_sales_paise"] == 1000
    assert rep_day1["total_returns_paise"] == 0
    assert rep_day1["net_sales_paise"] == 1000
    assert rep_day1["gross_profit_paise"] == 500

    rep_day2 = client.get("/reports/daily-summary?date=2026-06-11", headers=owner_headers).json()
    assert rep_day2["sales_count"] == 0
    assert rep_day2["returns_count"] == 1
    assert rep_day2["total_sales_paise"] == 0
    assert rep_day2["total_returns_paise"] == 1000
    assert rep_day2["net_sales_paise"] == -1000
    assert rep_day2["total_cost_paise"] == -500
    assert rep_day2["gross_profit_paise"] == -500


def test_top_selling_with_date_range(
    client: TestClient,
    owner_headers: dict[str, str],
    temp_db: str,
) -> None:
    from app.db import get_connection

    p_in = create_product(client, owner_headers, sku="TOP_IN_RANGE", name="Inside Range", price_paise=1000, cost_paise=500, stock=20)
    p_out = create_product(client, owner_headers, sku="TOP_OUT_RANGE", name="Outside Range", price_paise=1000, cost_paise=500, stock=20)

    conn = get_connection(temp_db)
    u_id = conn.execute("SELECT id FROM users WHERE role = 'owner'").fetchone()["id"]

    s1 = conn.execute(
        "INSERT INTO sales (customer_id, user_id, payment_type, total_paise, created_at) VALUES (NULL, ?, 'cash', 5000, '2026-07-01T10:00:00+00:00')",
        (u_id,),
    )
    s1_id = int(s1.lastrowid)
    conn.execute(
        "INSERT INTO sale_items (sale_id, product_id, qty, unit_price_paise, unit_cost_paise, line_total_paise) VALUES (?, ?, 5, 1000, 500, 5000)",
        (s1_id, p_out),
    )

    s2 = conn.execute(
        "INSERT INTO sales (customer_id, user_id, payment_type, total_paise, created_at) VALUES (NULL, ?, 'cash', 8000, '2026-07-15T10:00:00+00:00')",
        (u_id,),
    )
    s2_id = int(s2.lastrowid)
    conn.execute(
        "INSERT INTO sale_items (sale_id, product_id, qty, unit_price_paise, unit_cost_paise, line_total_paise) VALUES (?, ?, 8, 1000, 500, 8000)",
        (s2_id, p_in),
    )
    conn.close()

    res = client.get("/reports/top-selling?start_date=2026-07-10&end_date=2026-07-20", headers=owner_headers)
    assert res.status_code == 200
    items = res.json()
    p_ids = [it["product_id"] for it in items]
    assert p_in in p_ids
    assert p_out not in p_ids


def test_seeded_store_daily_summary_has_nonzero_cogs(tmp_path) -> None:
    import sys
    import os
    import subprocess
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    from app.db import get_connection
    from app.services.reports import get_daily_summary

    seed_db = str(tmp_path / "seed_cogs_test.db")
    env = os.environ.copy()
    env["STORESTOCK_DB_PATH"] = seed_db

    python_binary = sys.executable
    seed_proc = subprocess.run(
        [python_binary, "-m", "scripts.seed"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert seed_proc.returncode == 0

    kolkata_tz = ZoneInfo("Asia/Kolkata")
    now_k = datetime.now(kolkata_tz)
    check_days = [(now_k - timedelta(days=d)).strftime("%Y-%m-%d") for d in [0, 1, 5, 10, 14, 15, 20, 25, 29]]

    conn = get_connection(seed_db)
    for date_str in check_days:
        summary = get_daily_summary(conn, date_str)
        assert summary.sales_count > 0
        assert summary.total_sales_paise > 0
        assert summary.total_cost_paise > 0
        assert summary.gross_profit_paise > 0
        assert summary.gross_profit_paise == summary.net_sales_paise - summary.total_cost_paise
    conn.close()


def test_staff_cannot_see_cost_in_any_get_endpoint(
    client: TestClient,
    owner_headers: dict[str, str],
    staff_headers: dict[str, str],
) -> None:
    prod_id = create_product(client, owner_headers, sku="STAFF_AUDIT_P", name="Audit Item", price_paise=1000, cost_paise=600, stock=20)

    cust_res = client.post(
        "/customers",
        json={"name": "Audit Customer", "credit_limit_paise": 50000},
        headers=owner_headers,
    )
    cust_id = cust_res.json()["id"]

    sale_res = client.post(
        "/sales",
        json={"payment_type": "credit", "customer_id": cust_id, "items": [{"product_id": prod_id, "qty": 2}]},
        headers=owner_headers,
    )
    sale_id = sale_res.json()["id"]

    sup_res = client.post(
        "/suppliers",
        json={"name": "Audit Supplier"},
        headers=owner_headers,
    )
    sup_id = sup_res.json()["id"]

    po_res = client.post(
        "/purchase-orders",
        json={"supplier_id": sup_id, "items": [{"product_id": prod_id, "qty_ordered": 10, "unit_cost_paise": 500}]},
        headers=owner_headers,
    )
    po_id = po_res.json()["id"]

    def assert_no_cost_keys(data, path=""):
        if isinstance(data, dict):
            for k, v in data.items():
                assert "cost" not in k.lower(), f"Found 'cost' in key '{k}' at path '{path}.{k}'"
                assert_no_cost_keys(v, f"{path}.{k}")
        elif isinstance(data, list):
            for idx, item in enumerate(data):
                assert_no_cost_keys(item, f"{path}[{idx}]")

    staff_accessible_get_endpoints = [
        "/users/me",
        "/products",
        f"/products/{prod_id}",
        f"/products/{prod_id}/movements",
        "/stock",
        "/stock/low",
        "/sales",
        f"/sales/{sale_id}",
        "/customers",
        f"/customers/{cust_id}",
        f"/customers/{cust_id}/balance",
        f"/customers/{cust_id}/ledger",
        "/suppliers",
        f"/suppliers/{sup_id}",
        "/purchase-orders",
        f"/purchase-orders/{po_id}",
        "/purchase-orders/suggest",
    ]

    for ep in staff_accessible_get_endpoints:
        res = client.get(ep, headers=staff_headers)
        assert res.status_code == 200, f"Expected 200 on {ep}, got {res.status_code}: {res.text}"
        assert_no_cost_keys(res.json(), ep)

    owner_only_get_endpoints = [
        "/reports/daily-summary",
        "/reports/top-selling",
        "/reports/credit-summary",
        "/reports/inventory-valuation",
    ]

    for ep in owner_only_get_endpoints:
        res = client.get(ep, headers=staff_headers)
        assert res.status_code == 403, f"Expected 403 on {ep}, got {res.status_code}"
        assert_no_cost_keys(res.json(), ep)


