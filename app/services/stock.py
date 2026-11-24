import json
import sqlite3
from datetime import datetime, timezone
from fastapi import HTTPException, status
from app.db import transaction
from app.models.stock import (
    StockLevelResponse,
    StockMovementResponse,
    StockAdjustmentCreate,
    StockAdjustmentResponse,
)


def get_stock_levels(conn: sqlite3.Connection) -> list[StockLevelResponse]:
    sql = (
        "SELECT p.id AS product_id, p.sku, p.name, p.unit, p.reorder_level, "
        "COALESCE(SUM(sm.qty_change), 0) AS current_stock "
        "FROM products p "
        "LEFT JOIN stock_movements sm ON p.id = sm.product_id "
        "WHERE p.active = 1 "
        "GROUP BY p.id "
        "ORDER BY p.id ASC"
    )
    cursor = conn.execute(sql)
    return [
        StockLevelResponse(
            product_id=int(row["product_id"]),
            sku=str(row["sku"]),
            name=str(row["name"]),
            unit=str(row["unit"]),
            reorder_level=int(row["reorder_level"]),
            current_stock=int(row["current_stock"]),
        )
        for row in cursor.fetchall()
    ]


def get_low_stock(conn: sqlite3.Connection) -> list[StockLevelResponse]:
    sql = (
        "SELECT p.id AS product_id, p.sku, p.name, p.unit, p.reorder_level, "
        "COALESCE(SUM(sm.qty_change), 0) AS current_stock "
        "FROM products p "
        "LEFT JOIN stock_movements sm ON p.id = sm.product_id "
        "WHERE p.active = 1 "
        "GROUP BY p.id "
        "HAVING current_stock <= p.reorder_level "
        "ORDER BY current_stock ASC, p.id ASC"
    )
    cursor = conn.execute(sql)
    return [
        StockLevelResponse(
            product_id=int(row["product_id"]),
            sku=str(row["sku"]),
            name=str(row["name"]),
            unit=str(row["unit"]),
            reorder_level=int(row["reorder_level"]),
            current_stock=int(row["current_stock"]),
        )
        for row in cursor.fetchall()
    ]


def get_product_movements(
    conn: sqlite3.Connection,
    product_id: int,
    limit: int = 50,
    offset: int = 0,
) -> list[StockMovementResponse]:
    product_check = conn.execute("SELECT id FROM products WHERE id = ?", (product_id,)).fetchone()
    if not product_check:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    limit = min(max(1, limit), 100)
    sql = (
        "SELECT id, product_id, qty_change, kind, ref_type, ref_id, user_id, note, created_at "
        "FROM stock_movements "
        "WHERE product_id = ? "
        "ORDER BY created_at DESC, id DESC "
        "LIMIT ? OFFSET ?"
    )
    cursor = conn.execute(sql, (product_id, limit, offset))
    return [
        StockMovementResponse(
            id=int(row["id"]),
            product_id=int(row["product_id"]),
            qty_change=int(row["qty_change"]),
            kind=str(row["kind"]),
            ref_type=str(row["ref_type"]) if row["ref_type"] is not None else None,
            ref_id=int(row["ref_id"]) if row["ref_id"] is not None else None,
            user_id=int(row["user_id"]),
            note=str(row["note"]) if row["note"] is not None else None,
            created_at=str(row["created_at"]),
        )
        for row in cursor.fetchall()
    ]


def create_adjustment(
    conn: sqlite3.Connection,
    user_id: int,
    data: StockAdjustmentCreate,
) -> StockAdjustmentResponse:
    reason = data.reason.strip()
    if not reason:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reason is required",
        )
    if data.qty_change == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="qty_change cannot be zero",
        )

    with transaction(conn):
        prod = conn.execute("SELECT id, active FROM products WHERE id = ?", (data.product_id,)).fetchone()
        if not prod:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found",
            )
        if not bool(prod["active"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Product is inactive",
            )

        stock_row = conn.execute(
            "SELECT COALESCE(SUM(qty_change), 0) AS current_stock FROM stock_movements WHERE product_id = ?",
            (data.product_id,),
        ).fetchone()
        current_stock = int(stock_row["current_stock"]) if stock_row else 0

        new_stock = current_stock + data.qty_change
        if new_stock < 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Adjustment would reduce stock below zero",
            )

        now_iso = datetime.now(timezone.utc).isoformat()
        cursor = conn.execute(
            "INSERT INTO stock_movements (product_id, qty_change, kind, user_id, note, created_at) VALUES (?, ?, 'adjustment', ?, ?, ?)",
            (data.product_id, data.qty_change, user_id, reason, now_iso),
        )
        movement_id = int(cursor.lastrowid)

        old_val = json.dumps({"current_stock": current_stock})
        new_val = json.dumps(
            {
                "current_stock": new_stock,
                "qty_change": data.qty_change,
                "reason": reason,
            }
        )
        conn.execute(
            "INSERT INTO audit_log (user_id, action, entity_type, entity_id, old_value, new_value, created_at) VALUES (?, 'adjustment', 'stock', ?, ?, ?, ?)",
            (user_id, data.product_id, old_val, new_val, now_iso),
        )

    return StockAdjustmentResponse(
        id=movement_id,
        product_id=data.product_id,
        qty_change=data.qty_change,
        kind="adjustment",
        current_stock=new_stock,
        reason=reason,
        created_at=now_iso,
    )
