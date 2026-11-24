import io
import json
from fastapi.testclient import TestClient
from app.db import get_connection


def test_owner_create_product(client: TestClient, owner_headers: dict[str, str]) -> None:
    payload = {
        "sku": "PARLE_G_100",
        "name": "Parle-G Biscuit 100g",
        "unit": "pcs",
        "price_paise": 1000,
        "cost_paise": 800,
        "reorder_level": 20,
    }
    response = client.post("/products", json=payload, headers=owner_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["sku"] == "PARLE_G_100"
    assert data["name"] == "Parle-G Biscuit 100g"
    assert data["unit"] == "pcs"
    assert data["price_paise"] == 1000
    assert data["cost_paise"] == 800
    assert data["reorder_level"] == 20
    assert data["active"] is True
    assert "id" in data
    assert "created_at" in data


def test_create_product_duplicate_sku(client: TestClient, owner_headers: dict[str, str]) -> None:
    payload = {
        "sku": "UNIQUE_SKU_1",
        "name": "Item 1",
        "unit": "pcs",
        "price_paise": 500,
        "cost_paise": 400,
        "reorder_level": 5,
    }
    first_res = client.post("/products", json=payload, headers=owner_headers)
    assert first_res.status_code == 201

    second_res = client.post("/products", json=payload, headers=owner_headers)
    assert second_res.status_code == 409
    assert second_res.json() == {"detail": "SKU already exists"}


def test_staff_cannot_create_product(client: TestClient, staff_headers: dict[str, str]) -> None:
    payload = {
        "sku": "STAFF_PROD_1",
        "name": "Staff Item",
        "unit": "pcs",
        "price_paise": 500,
        "cost_paise": 400,
        "reorder_level": 5,
    }
    response = client.post("/products", json=payload, headers=staff_headers)
    assert response.status_code == 403
    assert response.json() == {"detail": "Owner permission required"}


def test_create_product_huge_price_rejected_422(
    client: TestClient,
    owner_headers: dict[str, str],
) -> None:
    res = client.post(
        "/products",
        json={"sku": "HUGE_PRICE_SKU", "name": "Item", "unit": "pcs", "price_paise": 10**13, "cost_paise": 100},
        headers=owner_headers,
    )
    assert res.status_code == 422


def test_csv_import_huge_value_rejected_with_row_number(
    client: TestClient,
    owner_headers: dict[str, str],
) -> None:
    csv_data = "sku,name,unit,price_paise,cost_paise,reorder_level,opening_qty\nHUGE_VAL,Item,pcs,10000000000000,80,5,10\n"
    response = client.post(
        "/products/import",
        files={"file": ("products.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")},
        headers=owner_headers,
    )
    assert response.status_code == 400
    assert "Row 2: price_paise exceeds maximum allowed limit" in response.json()["detail"]


def test_unauthenticated_cannot_create_product(client: TestClient) -> None:
    payload = {
        "sku": "NO_AUTH_PROD",
        "name": "No Auth Item",
        "unit": "pcs",
        "price_paise": 500,
        "cost_paise": 400,
    }
    response = client.post("/products", json=payload)
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_get_products_owner_sees_cost(client: TestClient, owner_headers: dict[str, str]) -> None:
    client.post(
        "/products",
        json={
            "sku": "PROD_A",
            "name": "Product Alpha",
            "unit": "pcs",
            "price_paise": 1500,
            "cost_paise": 1100,
            "reorder_level": 10,
        },
        headers=owner_headers,
    )
    response = client.get("/products", headers=owner_headers)
    assert response.status_code == 200
    items = response.json()
    assert len(items) >= 1
    target = next(item for item in items if item["sku"] == "PROD_A")
    assert "cost_paise" in target
    assert target["cost_paise"] == 1100


def test_get_products_staff_never_sees_cost(
    client: TestClient,
    owner_headers: dict[str, str],
    staff_headers: dict[str, str],
) -> None:
    client.post(
        "/products",
        json={
            "sku": "PROD_B",
            "name": "Product Beta",
            "unit": "pcs",
            "price_paise": 2000,
            "cost_paise": 1400,
            "reorder_level": 5,
        },
        headers=owner_headers,
    )
    response = client.get("/products", headers=staff_headers)
    assert response.status_code == 200
    items = response.json()
    assert len(items) >= 1
    for item in items:
        assert "cost_paise" not in item


def test_get_product_by_id_permissions(
    client: TestClient,
    owner_headers: dict[str, str],
    staff_headers: dict[str, str],
) -> None:
    res = client.post(
        "/products",
        json={
            "sku": "PROD_C",
            "name": "Product Gamma",
            "unit": "pcs",
            "price_paise": 3000,
            "cost_paise": 2100,
            "reorder_level": 5,
        },
        headers=owner_headers,
    )
    prod_id = res.json()["id"]

    owner_res = client.get(f"/products/{prod_id}", headers=owner_headers)
    assert owner_res.status_code == 200
    assert "cost_paise" in owner_res.json()
    assert owner_res.json()["cost_paise"] == 2100

    staff_res = client.get(f"/products/{prod_id}", headers=staff_headers)
    assert staff_res.status_code == 200
    assert "cost_paise" not in staff_res.json()
    assert staff_res.json()["sku"] == "PROD_C"


def test_get_product_not_found(client: TestClient, owner_headers: dict[str, str]) -> None:
    response = client.get("/products/999999", headers=owner_headers)
    assert response.status_code == 404
    assert response.json() == {"detail": "Product not found"}


def test_search_products_by_name_and_sku(client: TestClient, owner_headers: dict[str, str]) -> None:
    client.post(
        "/products",
        json={
            "sku": "MAGGI_70G",
            "name": "Maggi 2-Minute Noodles",
            "unit": "pcs",
            "price_paise": 1400,
            "cost_paise": 1100,
            "reorder_level": 50,
        },
        headers=owner_headers,
    )
    client.post(
        "/products",
        json={
            "sku": "ATTA_5KG",
            "name": "Aashirvaad Shudh Chakki Atta",
            "unit": "pack",
            "price_paise": 24000,
            "cost_paise": 21000,
            "reorder_level": 10,
        },
        headers=owner_headers,
    )

    maggi_res = client.get("/products?q=maggi", headers=owner_headers)
    assert maggi_res.status_code == 200
    results = maggi_res.json()
    assert len(results) == 1
    assert results[0]["sku"] == "MAGGI_70G"

    atta_name_res = client.get("/products?q=CHAKKI", headers=owner_headers)
    assert atta_name_res.status_code == 200
    assert len(atta_name_res.json()) == 1
    assert atta_name_res.json()[0]["sku"] == "ATTA_5KG"

    atta_sku_res = client.get("/products?q=atta_5", headers=owner_headers)
    assert atta_sku_res.status_code == 200
    assert len(atta_sku_res.json()) == 1
    assert atta_sku_res.json()[0]["sku"] == "ATTA_5KG"


def test_filter_products_by_active(client: TestClient, owner_headers: dict[str, str]) -> None:
    res = client.post(
        "/products",
        json={
            "sku": "ACTIVE_FILTER_TEST",
            "name": "Filter Test Item",
            "unit": "pcs",
            "price_paise": 500,
            "cost_paise": 300,
        },
        headers=owner_headers,
    )
    prod_id = res.json()["id"]

    client.patch(f"/products/{prod_id}", json={"active": False}, headers=owner_headers)

    active_res = client.get("/products?active=true&q=ACTIVE_FILTER_TEST", headers=owner_headers)
    assert len(active_res.json()) == 0

    inactive_res = client.get("/products?active=false&q=ACTIVE_FILTER_TEST", headers=owner_headers)
    assert len(inactive_res.json()) == 1
    assert inactive_res.json()[0]["sku"] == "ACTIVE_FILTER_TEST"


def test_patch_product_price_and_cost_writes_audit_log(
    client: TestClient,
    owner_headers: dict[str, str],
    temp_db: str,
) -> None:
    res = client.post(
        "/products",
        json={
            "sku": "AUDIT_PROD_1",
            "name": "Audit Item",
            "unit": "pcs",
            "price_paise": 1000,
            "cost_paise": 800,
            "reorder_level": 5,
        },
        headers=owner_headers,
    )
    prod_id = res.json()["id"]

    patch_res = client.patch(
        f"/products/{prod_id}",
        json={"price_paise": 1200, "cost_paise": 950},
        headers=owner_headers,
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["price_paise"] == 1200
    assert patch_res.json()["cost_paise"] == 950

    conn = get_connection(temp_db)
    cursor = conn.execute(
        "SELECT user_id, action, entity_type, entity_id, old_value, new_value FROM audit_log WHERE entity_id = ? AND entity_type = 'product'",
        (prod_id,),
    )
    audit_rows = cursor.fetchall()
    conn.close()

    assert len(audit_rows) == 1
    row = audit_rows[0]
    assert row["action"] == "update"
    assert row["entity_type"] == "product"
    assert row["entity_id"] == prod_id
    old_data = json.loads(row["old_value"])
    new_data = json.loads(row["new_value"])
    assert old_data == {"price_paise": 1000, "cost_paise": 800}
    assert new_data == {"price_paise": 1200, "cost_paise": 950}


def test_patch_product_non_price_fields_no_audit(
    client: TestClient,
    owner_headers: dict[str, str],
    temp_db: str,
) -> None:
    res = client.post(
        "/products",
        json={
            "sku": "NO_AUDIT_PROD",
            "name": "Initial Name",
            "unit": "pcs",
            "price_paise": 1000,
            "cost_paise": 800,
        },
        headers=owner_headers,
    )
    prod_id = res.json()["id"]

    patch_res = client.patch(
        f"/products/{prod_id}",
        json={"name": "Renamed Item", "unit": "pack"},
        headers=owner_headers,
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["name"] == "Renamed Item"
    assert patch_res.json()["unit"] == "pack"

    conn = get_connection(temp_db)
    cursor = conn.execute("SELECT id FROM audit_log WHERE entity_id = ? AND entity_type = 'product'", (prod_id,))
    rows = cursor.fetchall()
    conn.close()
    assert len(rows) == 0


def test_staff_cannot_patch_product(
    client: TestClient,
    owner_headers: dict[str, str],
    staff_headers: dict[str, str],
) -> None:
    res = client.post(
        "/products",
        json={
            "sku": "PATCH_STAFF_GUARD",
            "name": "Guarded Item",
            "unit": "pcs",
            "price_paise": 1000,
            "cost_paise": 800,
        },
        headers=owner_headers,
    )
    prod_id = res.json()["id"]

    patch_res = client.patch(
        f"/products/{prod_id}",
        json={"name": "Tampered By Staff"},
        headers=staff_headers,
    )
    assert patch_res.status_code == 403
    assert patch_res.json() == {"detail": "Owner permission required"}


def test_csv_import_valid(
    client: TestClient,
    owner_headers: dict[str, str],
    temp_db: str,
) -> None:
    csv_data = "sku,name,unit,price_paise,cost_paise,reorder_level,opening_qty\nCSV_1,Item One,pcs,100,80,5,25\nCSV_2,Item Two,pack,200,160,10,0\n"
    response = client.post(
        "/products/import",
        files={"file": ("products.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")},
        headers=owner_headers,
    )
    assert response.status_code == 200
    assert response.json() == {"imported": 2}

    conn = get_connection(temp_db)
    prod1 = conn.execute("SELECT id FROM products WHERE sku = 'CSV_1'").fetchone()
    prod2 = conn.execute("SELECT id FROM products WHERE sku = 'CSV_2'").fetchone()
    assert prod1 is not None
    assert prod2 is not None

    movements1 = conn.execute(
        "SELECT qty_change, kind FROM stock_movements WHERE product_id = ?",
        (prod1["id"],),
    ).fetchall()
    assert len(movements1) == 1
    assert movements1[0]["qty_change"] == 25
    assert movements1[0]["kind"] == "opening"

    movements2 = conn.execute(
        "SELECT qty_change FROM stock_movements WHERE product_id = ?",
        (prod2["id"],),
    ).fetchall()
    assert len(movements2) == 0
    conn.close()


def test_csv_import_all_or_nothing_with_bad_row(
    client: TestClient,
    owner_headers: dict[str, str],
    temp_db: str,
) -> None:
    csv_data = "sku,name,unit,price_paise,cost_paise,reorder_level,opening_qty\nBAD_ROW_1,Good Item 1,pcs,100,80,5,10\nBAD_ROW_2,Bad Item 2,pcs,-50,80,5,10\nBAD_ROW_3,Good Item 3,pcs,100,80,5,10\n"
    response = client.post(
        "/products/import",
        files={"file": ("products.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")},
        headers=owner_headers,
    )
    assert response.status_code == 400
    assert "Row 3: price_paise must be a whole non-negative integer" in response.json()["detail"]

    conn = get_connection(temp_db)
    count = conn.execute("SELECT COUNT(*) AS total FROM products WHERE sku LIKE 'BAD_ROW_%'").fetchone()["total"]
    conn.close()
    assert count == 0


def test_csv_import_duplicate_sku_in_file(
    client: TestClient,
    owner_headers: dict[str, str],
    temp_db: str,
) -> None:
    csv_data = "sku,name,unit,price_paise,cost_paise,reorder_level,opening_qty\nDUPE_FILE_SKU,First Occurrence,pcs,100,80,5,10\nDUPE_FILE_SKU,Second Occurrence,pcs,100,80,5,10\n"
    response = client.post(
        "/products/import",
        files={"file": ("products.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")},
        headers=owner_headers,
    )
    assert response.status_code == 400
    assert "Duplicate SKU 'DUPE_FILE_SKU' in file" in response.json()["detail"]

    conn = get_connection(temp_db)
    count = conn.execute("SELECT COUNT(*) AS total FROM products WHERE sku = 'DUPE_FILE_SKU'").fetchone()["total"]
    conn.close()
    assert count == 0


def test_csv_import_sku_already_in_database(
    client: TestClient,
    owner_headers: dict[str, str],
    temp_db: str,
) -> None:
    client.post(
        "/products",
        json={
            "sku": "EXISTING_DB_SKU",
            "name": "Pre-existing Item",
            "unit": "pcs",
            "price_paise": 100,
            "cost_paise": 80,
        },
        headers=owner_headers,
    )
    csv_data = "sku,name,unit,price_paise,cost_paise,reorder_level,opening_qty\nEXISTING_DB_SKU,Import Attempt,pcs,100,80,5,10\n"
    response = client.post(
        "/products/import",
        files={"file": ("products.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")},
        headers=owner_headers,
    )
    assert response.status_code == 400
    assert "SKU 'EXISTING_DB_SKU' already exists in database" in response.json()["detail"]


def test_csv_import_missing_columns(client: TestClient, owner_headers: dict[str, str]) -> None:
    csv_data = "sku,name,unit,price_paise\nINCOMPLETE,Incomplete Item,pcs,100\n"
    response = client.post(
        "/products/import",
        files={"file": ("products.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")},
        headers=owner_headers,
    )
    assert response.status_code == 400
    assert "Missing required columns" in response.json()["detail"]


def test_csv_import_empty_file(client: TestClient, owner_headers: dict[str, str]) -> None:
    csv_data = "   \n  \n"
    response = client.post(
        "/products/import",
        files={"file": ("products.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")},
        headers=owner_headers,
    )
    assert response.status_code == 400
    assert "CSV file is empty" in response.json()["detail"]


def test_csv_import_non_numeric_values(client: TestClient, owner_headers: dict[str, str]) -> None:
    csv_data = "sku,name,unit,price_paise,cost_paise,reorder_level,opening_qty\nNON_NUM,Item,pcs,not_a_number,80,5,10\n"
    response = client.post(
        "/products/import",
        files={"file": ("products.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")},
        headers=owner_headers,
    )
    assert response.status_code == 400
    assert "price_paise must be a whole non-negative integer" in response.json()["detail"]


def test_csv_import_excel_bom(
    client: TestClient,
    owner_headers: dict[str, str],
    temp_db: str,
) -> None:
    csv_data = "\ufeffsku,name,unit,price_paise,cost_paise,reorder_level,opening_qty\nEXCEL_BOM_SKU,Bom Item,pcs,100,80,5,10\n"
    response = client.post(
        "/products/import",
        files={"file": ("products.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")},
        headers=owner_headers,
    )
    assert response.status_code == 200
    assert response.json() == {"imported": 1}

    conn = get_connection(temp_db)
    row = conn.execute("SELECT sku, name FROM products WHERE sku = 'EXCEL_BOM_SKU'").fetchone()
    conn.close()
    assert row is not None
    assert row["sku"] == "EXCEL_BOM_SKU"


def test_csv_import_opening_qty_zero(
    client: TestClient,
    owner_headers: dict[str, str],
    temp_db: str,
) -> None:
    csv_data = "sku,name,unit,price_paise,cost_paise,reorder_level,opening_qty\nZERO_QTY_SKU,Zero Qty Item,pcs,100,80,5,0\n"
    response = client.post(
        "/products/import",
        files={"file": ("products.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")},
        headers=owner_headers,
    )
    assert response.status_code == 200
    assert response.json() == {"imported": 1}

    conn = get_connection(temp_db)
    prod = conn.execute("SELECT id FROM products WHERE sku = 'ZERO_QTY_SKU'").fetchone()
    assert prod is not None
    movements = conn.execute("SELECT id FROM stock_movements WHERE product_id = ?", (prod["id"],)).fetchall()
    conn.close()
    assert len(movements) == 0


def test_csv_import_rejects_floating_point_numbers(
    client: TestClient,
    owner_headers: dict[str, str],
) -> None:
    csv_data = "sku,name,unit,price_paise,cost_paise,reorder_level,opening_qty\nFLOAT_TEST,Item,pcs,10.50,80,5,10\n"
    response = client.post(
        "/products/import",
        files={"file": ("products.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")},
        headers=owner_headers,
    )
    assert response.status_code == 400
    assert "Row 2: price_paise must be a whole non-negative integer" in response.json()["detail"]


def test_csv_import_rejects_non_ascii_unicode_digits(
    client: TestClient,
    owner_headers: dict[str, str],
) -> None:
    csv_data = "sku,name,unit,price_paise,cost_paise,reorder_level,opening_qty\nSUPERSCRIPT_SKU,Item,pcs,10\u00b2,80,5,10\nARABIC_SKU,Item,pcs,100,\u0665\u0660,5,10\n"
    response = client.post(
        "/products/import",
        files={"file": ("products.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")},
        headers=owner_headers,
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "Row 2: price_paise must be a whole non-negative integer" in detail
    assert "Row 3: cost_paise must be a whole non-negative integer" in detail


def test_search_escapes_wildcards(client: TestClient, owner_headers: dict[str, str]) -> None:
    client.post(
        "/products",
        json={
            "sku": "GHEE_PERCENT",
            "name": "100% Pure Ghee",
            "unit": "pack",
            "price_paise": 50000,
            "cost_paise": 45000,
        },
        headers=owner_headers,
    )
    client.post(
        "/products",
        json={
            "sku": "GHEE_PLAIN",
            "name": "100 Pure Ghee",
            "unit": "pack",
            "price_paise": 48000,
            "cost_paise": 43000,
        },
        headers=owner_headers,
    )
    client.post(
        "/products",
        json={
            "sku": "UNDERSCORE_ITEM",
            "name": "ITEM_ONE",
            "unit": "pcs",
            "price_paise": 100,
            "cost_paise": 80,
        },
        headers=owner_headers,
    )
    client.post(
        "/products",
        json={
            "sku": "MATCH_ANY_CHAR",
            "name": "ITEMXONE",
            "unit": "pcs",
            "price_paise": 100,
            "cost_paise": 80,
        },
        headers=owner_headers,
    )

    percent_res = client.get("/products?q=100%", headers=owner_headers)
    assert percent_res.status_code == 200
    assert len(percent_res.json()) == 1
    assert percent_res.json()[0]["sku"] == "GHEE_PERCENT"

    underscore_res = client.get("/products?q=ITEM_ONE", headers=owner_headers)
    assert underscore_res.status_code == 200
    assert len(underscore_res.json()) == 1
    assert underscore_res.json()[0]["sku"] == "UNDERSCORE_ITEM"


def test_sku_uniqueness_case_insensitive_and_trimmed(
    client: TestClient,
    owner_headers: dict[str, str],
) -> None:
    create_res = client.post(
        "/products",
        json={
            "sku": "  Case_Sensitive_SKU  ",
            "name": "  Trimmed Name  ",
            "unit": "pcs",
            "price_paise": 200,
            "cost_paise": 150,
        },
        headers=owner_headers,
    )
    assert create_res.status_code == 201
    assert create_res.json()["sku"] == "Case_Sensitive_SKU"
    assert create_res.json()["name"] == "Trimmed Name"

    dup_case_res = client.post(
        "/products",
        json={
            "sku": "case_sensitive_sku",
            "name": "Different Name",
            "unit": "pcs",
            "price_paise": 200,
            "cost_paise": 150,
        },
        headers=owner_headers,
    )
    assert dup_case_res.status_code == 409
    assert dup_case_res.json() == {"detail": "SKU already exists"}

    csv_data = "sku,name,unit,price_paise,cost_paise,reorder_level,opening_qty\nCASE_SENSITIVE_SKU,Import Attempt,pcs,200,150,5,10\n"
    csv_res = client.post(
        "/products/import",
        files={"file": ("products.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")},
        headers=owner_headers,
    )
    assert csv_res.status_code == 400
    assert "already exists in database" in csv_res.json()["detail"]


def test_limit_capped_at_100(client: TestClient, owner_headers: dict[str, str]) -> None:
    response = client.get("/products?limit=150", headers=owner_headers)
    assert response.status_code == 422


def test_csv_upload_over_1mb_rejected_with_413(
    client: TestClient,
    owner_headers: dict[str, str],
) -> None:
    oversized_data = b"sku,name,unit,price_paise,cost_paise,reorder_level,opening_qty\n" + b"X" * (1024 * 1024 + 10)
    response = client.post(
        "/products/import",
        files={"file": ("large.csv", io.BytesIO(oversized_data), "text/csv")},
        headers=owner_headers,
    )
    assert response.status_code == 413
    assert response.json() == {"detail": "CSV upload exceeds 1 MB limit"}


def test_staff_cannot_import_csv(client: TestClient, staff_headers: dict[str, str]) -> None:
    csv_data = "sku,name,unit,price_paise,cost_paise,reorder_level,opening_qty\nSTAFF_IMPORT,Item,pcs,100,80,5,10\n"
    response = client.post(
        "/products/import",
        files={"file": ("products.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")},
        headers=staff_headers,
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "Owner permission required"}


def test_create_product_huge_price_rejected_422(
    client: TestClient,
    owner_headers: dict[str, str],
) -> None:
    res = client.post(
        "/products",
        json={"sku": "HUGE_PRICE_SKU", "name": "Item", "unit": "pcs", "price_paise": 10**13, "cost_paise": 100},
        headers=owner_headers,
    )
    assert res.status_code == 422


def test_csv_import_huge_value_rejected_with_row_number(
    client: TestClient,
    owner_headers: dict[str, str],
) -> None:
    csv_data = "sku,name,unit,price_paise,cost_paise,reorder_level,opening_qty\nHUGE_VAL,Item,pcs,10000000000000,80,5,10\n"
    response = client.post(
        "/products/import",
        files={"file": ("products.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")},
        headers=owner_headers,
    )
    assert response.status_code == 400
    assert "Row 2: price_paise exceeds maximum allowed limit" in response.json()["detail"]
