import csv
import io
import json
import re
import sqlite3
from datetime import datetime, timezone
from typing import Any
from fastapi import HTTPException, status
from app.db import transaction
from app.models.products import ProductCreate, ProductUpdate, ProductResponse, ProductImportResponse


def create_product(conn: sqlite3.Connection, data: ProductCreate) -> ProductResponse:
    sku = data.sku.strip()
    name = data.name.strip()
    cursor = conn.execute("SELECT id FROM products WHERE sku = ? COLLATE NOCASE", (sku,))
    if cursor.fetchone():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="SKU already exists",
        )
    created_at = datetime.now(timezone.utc).isoformat()
    cursor = conn.execute(
        "INSERT INTO products (sku, name, unit, price_paise, cost_paise, reorder_level, active, created_at) VALUES (?, ?, ?, ?, ?, ?, 1, ?)",
        (sku, name, data.unit, data.price_paise, data.cost_paise, data.reorder_level, created_at),
    )
    new_id = int(cursor.lastrowid)
    return ProductResponse(
        id=new_id,
        sku=sku,
        name=name,
        unit=data.unit,
        price_paise=data.price_paise,
        cost_paise=data.cost_paise,
        reorder_level=data.reorder_level,
        active=True,
        created_at=created_at,
    )


def get_product_by_id(conn: sqlite3.Connection, product_id: int) -> dict[str, Any] | None:
    cursor = conn.execute(
        "SELECT id, sku, name, unit, price_paise, cost_paise, reorder_level, active, created_at FROM products WHERE id = ?",
        (product_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    return {
        "id": int(row["id"]),
        "sku": str(row["sku"]),
        "name": str(row["name"]),
        "unit": str(row["unit"]),
        "price_paise": int(row["price_paise"]),
        "cost_paise": int(row["cost_paise"]),
        "reorder_level": int(row["reorder_level"]),
        "active": bool(row["active"]),
        "created_at": str(row["created_at"]),
    }


def list_products(
    conn: sqlite3.Connection,
    q: str = "",
    active: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    limit = min(max(1, limit), 100)
    conditions: list[str] = []
    params: list[Any] = []
    if q:
        escaped_q = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        search_term = f"%{escaped_q.lower()}%"
        conditions.append("(LOWER(name) LIKE ? ESCAPE '\\' OR LOWER(sku) LIKE ? ESCAPE '\\')")
        params.extend([search_term, search_term])
    if active is not None:
        conditions.append("active = ?")
        params.append(1 if active else 0)

    where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"SELECT id, sku, name, unit, price_paise, cost_paise, reorder_level, active, created_at FROM products{where_clause} ORDER BY id ASC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor = conn.execute(sql, params)
    results: list[dict[str, Any]] = []
    for row in cursor.fetchall():
        results.append(
            {
                "id": int(row["id"]),
                "sku": str(row["sku"]),
                "name": str(row["name"]),
                "unit": str(row["unit"]),
                "price_paise": int(row["price_paise"]),
                "cost_paise": int(row["cost_paise"]),
                "reorder_level": int(row["reorder_level"]),
                "active": bool(row["active"]),
                "created_at": str(row["created_at"]),
            }
        )
    return results


def update_product(
    conn: sqlite3.Connection,
    product_id: int,
    user_id: int,
    data: ProductUpdate,
) -> ProductResponse:
    current = get_product_by_id(conn, product_id)
    if not current:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    fields: list[str] = []
    params: list[Any] = []
    price_changed = False
    cost_changed = False

    if data.name is not None:
        fields.append("name = ?")
        params.append(data.name.strip())
    if data.unit is not None:
        fields.append("unit = ?")
        params.append(data.unit)
    if data.price_paise is not None and data.price_paise != current["price_paise"]:
        fields.append("price_paise = ?")
        params.append(data.price_paise)
        price_changed = True
    if data.cost_paise is not None and data.cost_paise != current["cost_paise"]:
        fields.append("cost_paise = ?")
        params.append(data.cost_paise)
        cost_changed = True
    if data.reorder_level is not None:
        fields.append("reorder_level = ?")
        params.append(data.reorder_level)
    if data.active is not None:
        fields.append("active = ?")
        params.append(1 if data.active else 0)

    if fields:
        with transaction(conn):
            params.append(product_id)
            conn.execute(f"UPDATE products SET {', '.join(fields)} WHERE id = ?", params)
            if price_changed or cost_changed:
                old_val = json.dumps(
                    {
                        "price_paise": current["price_paise"],
                        "cost_paise": current["cost_paise"],
                    }
                )
                new_val = json.dumps(
                    {
                        "price_paise": data.price_paise if data.price_paise is not None else current["price_paise"],
                        "cost_paise": data.cost_paise if data.cost_paise is not None else current["cost_paise"],
                    }
                )
                created_at = datetime.now(timezone.utc).isoformat()
                conn.execute(
                    "INSERT INTO audit_log (user_id, action, entity_type, entity_id, old_value, new_value, created_at) VALUES (?, 'update', 'product', ?, ?, ?, ?)",
                    (user_id, product_id, old_val, new_val, created_at),
                )

    updated = get_product_by_id(conn, product_id)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    return ProductResponse(**updated)


def import_products_csv(
    conn: sqlite3.Connection,
    user_id: int,
    content: str,
) -> ProductImportResponse:
    if not content or not content.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV file is empty",
        )

    file_stream = io.StringIO(content.strip())
    reader = csv.DictReader(file_stream)
    required_cols = {"sku", "name", "unit", "price_paise", "cost_paise", "reorder_level", "opening_qty"}

    if not reader.fieldnames or not required_cols.issubset(set(reader.fieldnames)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required columns in CSV header",
        )

    rows: list[dict[str, Any]] = []
    seen_file_skus: set[str] = set()
    errors: list[str] = []

    cursor = conn.execute("SELECT sku FROM products")
    existing_skus = {row["sku"].lower() for row in cursor.fetchall()}

    for row_idx, row in enumerate(reader, start=2):
        row_has_error = False

        sku = (row.get("sku") or "").strip()
        if not sku:
            errors.append(f"Row {row_idx}: SKU cannot be empty")
            row_has_error = True
        elif sku.lower() in seen_file_skus:
            errors.append(f"Row {row_idx}: Duplicate SKU '{sku}' in file")
            row_has_error = True
        elif sku.lower() in existing_skus:
            errors.append(f"Row {row_idx}: SKU '{sku}' already exists in database")
            row_has_error = True
        else:
            seen_file_skus.add(sku.lower())

        name = (row.get("name") or "").strip()
        if not name:
            errors.append(f"Row {row_idx}: Name cannot be empty")
            row_has_error = True

        unit = (row.get("unit") or "").strip()
        if not unit:
            errors.append(f"Row {row_idx}: Unit cannot be empty")
            row_has_error = True

        raw_price = (row.get("price_paise") or "").strip()
        if not re.fullmatch(r"[0-9]+", raw_price):
            errors.append(f"Row {row_idx}: price_paise must be a whole non-negative integer")
            row_has_error = True
        elif int(raw_price) > 10**12:
            errors.append(f"Row {row_idx}: price_paise exceeds maximum allowed limit")
            row_has_error = True
        else:
            price_paise = int(raw_price)

        raw_cost = (row.get("cost_paise") or "").strip()
        if not re.fullmatch(r"[0-9]+", raw_cost):
            errors.append(f"Row {row_idx}: cost_paise must be a whole non-negative integer")
            row_has_error = True
        elif int(raw_cost) > 10**12:
            errors.append(f"Row {row_idx}: cost_paise exceeds maximum allowed limit")
            row_has_error = True
        else:
            cost_paise = int(raw_cost)

        raw_reorder = (row.get("reorder_level") or "").strip()
        if not re.fullmatch(r"[0-9]+", raw_reorder):
            errors.append(f"Row {row_idx}: reorder_level must be a whole non-negative integer")
            row_has_error = True
        elif int(raw_reorder) > 100000:
            errors.append(f"Row {row_idx}: reorder_level exceeds maximum allowed limit")
            row_has_error = True
        else:
            reorder_level = int(raw_reorder)

        raw_opening = (row.get("opening_qty") or "").strip()
        if not re.fullmatch(r"[0-9]+", raw_opening):
            errors.append(f"Row {row_idx}: opening_qty must be a whole non-negative integer")
            row_has_error = True
        elif int(raw_opening) > 100000:
            errors.append(f"Row {row_idx}: opening_qty exceeds maximum allowed limit")
            row_has_error = True
        else:
            opening_qty = int(raw_opening)

        if not row_has_error:
            rows.append(
                {
                    "sku": sku,
                    "name": name,
                    "unit": unit,
                    "price_paise": price_paise,
                    "cost_paise": cost_paise,
                    "reorder_level": reorder_level,
                    "opening_qty": opening_qty,
                }
            )

    if not rows and not errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV file contains no data rows",
        )

    if errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="; ".join(errors),
        )

    now_iso = datetime.now(timezone.utc).isoformat()
    with transaction(conn):
        for item in rows:
            cursor = conn.execute(
                "INSERT INTO products (sku, name, unit, price_paise, cost_paise, reorder_level, active, created_at) VALUES (?, ?, ?, ?, ?, ?, 1, ?)",
                (
                    item["sku"],
                    item["name"],
                    item["unit"],
                    item["price_paise"],
                    item["cost_paise"],
                    item["reorder_level"],
                    now_iso,
                ),
            )
            product_id = int(cursor.lastrowid)
            if item["opening_qty"] > 0:
                conn.execute(
                    "INSERT INTO stock_movements (product_id, qty_change, kind, user_id, note, created_at) VALUES (?, ?, 'opening', ?, 'CSV import', ?)",
                    (product_id, item["opening_qty"], user_id, now_iso),
                )

    return ProductImportResponse(imported=len(rows))
