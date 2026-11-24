import sqlite3
from datetime import datetime, timezone
from fastapi import HTTPException, status
from app.db import transaction
from app.models.purchase_orders import (
    POCreate,
    POResponse,
    POItemResponse,
    POReceiveRequest,
    POSuggestionItem,
)


def get_purchase_order_by_id(conn: sqlite3.Connection, po_id: int) -> POResponse:
    po = conn.execute(
        "SELECT id, supplier_id, status, created_by, created_at, sent_at, received_at FROM purchase_orders WHERE id = ?",
        (po_id,),
    ).fetchone()
    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase order not found",
        )

    items_cursor = conn.execute(
        "SELECT id, purchase_order_id, product_id, qty_ordered, qty_received, unit_cost_paise "
        "FROM purchase_order_items WHERE purchase_order_id = ? ORDER BY id ASC",
        (po_id,),
    )
    items = [
        POItemResponse(
            id=int(row["id"]),
            purchase_order_id=int(row["purchase_order_id"]),
            product_id=int(row["product_id"]),
            qty_ordered=int(row["qty_ordered"]),
            qty_received=int(row["qty_received"]),
            unit_cost_paise=int(row["unit_cost_paise"]),
        )
        for row in items_cursor.fetchall()
    ]

    return POResponse(
        id=int(po["id"]),
        supplier_id=int(po["supplier_id"]),
        status=str(po["status"]),
        created_by=int(po["created_by"]),
        created_at=str(po["created_at"]),
        sent_at=str(po["sent_at"]) if po["sent_at"] is not None else None,
        received_at=str(po["received_at"]) if po["received_at"] is not None else None,
        items=items,
    )


def create_purchase_order(
    conn: sqlite3.Connection,
    user_id: int,
    data: POCreate,
) -> POResponse:
    if not data.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Purchase order must contain at least one item",
        )

    if len(data.items) > 200:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Purchase order cannot contain more than 200 items",
        )

    pids = [item.product_id for item in data.items]
    if len(pids) != len(set(pids)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Duplicate product lines in purchase order",
        )

    sup = conn.execute(
        "SELECT id, active FROM suppliers WHERE id = ?",
        (data.supplier_id,),
    ).fetchone()
    if not sup:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found",
        )
    if not bool(sup["active"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Supplier is inactive",
        )

    for item in data.items:
        prod = conn.execute(
            "SELECT id, active FROM products WHERE id = ?",
            (item.product_id,),
        ).fetchone()
        if not prod:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product {item.product_id} not found",
            )
        if not bool(prod["active"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Product {item.product_id} is inactive",
            )

    now_iso = datetime.now(timezone.utc).isoformat()
    with transaction(conn):
        cursor = conn.execute(
            "INSERT INTO purchase_orders (supplier_id, status, created_by, created_at, sent_at, received_at) "
            "VALUES (?, 'draft', ?, ?, NULL, NULL)",
            (data.supplier_id, user_id, now_iso),
        )
        po_id = int(cursor.lastrowid)

        for item in data.items:
            conn.execute(
                "INSERT INTO purchase_order_items (purchase_order_id, product_id, qty_ordered, qty_received, unit_cost_paise) "
                "VALUES (?, ?, ?, 0, ?)",
                (po_id, item.product_id, item.qty_ordered, item.unit_cost_paise),
            )

    return get_purchase_order_by_id(conn, po_id)


def list_purchase_orders(
    conn: sqlite3.Connection,
    status_filter: str | None = None,
    supplier_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[POResponse]:
    limit = min(max(1, limit), 100)
    conditions: list[str] = []
    params: list[str | int] = []

    if status_filter:
        conditions.append("status = ?")
        params.append(status_filter)

    if supplier_id is not None:
        conditions.append("supplier_id = ?")
        params.append(supplier_id)

    where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"SELECT id FROM purchase_orders{where_clause} ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor = conn.execute(sql, params)
    po_ids = [int(row["id"]) for row in cursor.fetchall()]

    return [get_purchase_order_by_id(conn, pid) for pid in po_ids]


def send_purchase_order(conn: sqlite3.Connection, po_id: int) -> POResponse:
    with transaction(conn):
        po = conn.execute(
            "SELECT status FROM purchase_orders WHERE id = ?",
            (po_id,),
        ).fetchone()
        if not po:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Purchase order not found",
            )
        if po["status"] != "draft":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot send purchase order in '{po['status']}' status",
            )

        now_iso = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE purchase_orders SET status = 'sent', sent_at = ? WHERE id = ?",
            (now_iso, po_id),
        )

    return get_purchase_order_by_id(conn, po_id)


def cancel_purchase_order(conn: sqlite3.Connection, po_id: int) -> POResponse:
    with transaction(conn):
        po = conn.execute(
            "SELECT status FROM purchase_orders WHERE id = ?",
            (po_id,),
        ).fetchone()
        if not po:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Purchase order not found",
            )
        if po["status"] not in ("draft", "sent"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot cancel purchase order in '{po['status']}' status",
            )

        conn.execute(
            "UPDATE purchase_orders SET status = 'cancelled' WHERE id = ?",
            (po_id,),
        )

    return get_purchase_order_by_id(conn, po_id)


def receive_purchase_order_items(
    conn: sqlite3.Connection,
    user_id: int,
    po_id: int,
    data: POReceiveRequest,
) -> POResponse:
    if not data.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Receive request must contain at least one item",
        )

    with transaction(conn):
        po = conn.execute(
            "SELECT status FROM purchase_orders WHERE id = ?",
            (po_id,),
        ).fetchone()
        if not po:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Purchase order not found",
            )
        if po["status"] not in ("sent", "partially_received"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot receive goods for purchase order in '{po['status']}' status",
            )

        rows = conn.execute(
            "SELECT id, product_id, qty_ordered, qty_received FROM purchase_order_items WHERE purchase_order_id = ?",
            (po_id,),
        ).fetchall()
        items_by_id = {int(r["id"]): dict(r) for r in rows}
        items_by_prod = {int(r["product_id"]): dict(r) for r in rows}

        target_items: list[tuple[dict[str, int], int]] = []
        for line in data.items:
            if line.qty <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Received quantity must be greater than zero",
                )

            target: dict[str, int] | None = None
            if line.item_id is not None:
                target = items_by_id.get(line.item_id)
                if target is None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Item {line.item_id} does not belong to this purchase order",
                    )
            elif line.product_id is not None:
                target = items_by_prod.get(line.product_id)
                if target is None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Product {line.product_id} does not belong to this purchase order",
                    )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Either item_id or product_id must be provided",
                )

            if target["qty_received"] + line.qty > target["qty_ordered"]:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Received quantity exceeds ordered quantity for product {target['product_id']}",
                )

            target["qty_received"] += line.qty
            target_items.append((target, line.qty))

        now_iso = datetime.now(timezone.utc).isoformat()
        for target, received_qty in target_items:
            conn.execute(
                "UPDATE purchase_order_items SET qty_received = ? WHERE id = ?",
                (target["qty_received"], target["id"]),
            )
            conn.execute(
                "INSERT INTO stock_movements (product_id, qty_change, kind, ref_type, ref_id, user_id, note, created_at) "
                "VALUES (?, ?, 'delivery', 'purchase_order', ?, ?, ?, ?)",
                (target["product_id"], received_qty, po_id, user_id, f"Receipt for PO #{po_id}", now_iso),
            )

        updated_rows = conn.execute(
            "SELECT qty_ordered, qty_received FROM purchase_order_items WHERE purchase_order_id = ?",
            (po_id,),
        ).fetchall()
        all_received = all(int(r["qty_received"]) == int(r["qty_ordered"]) for r in updated_rows)

        if all_received:
            conn.execute(
                "UPDATE purchase_orders SET status = 'received', received_at = ? WHERE id = ?",
                (now_iso, po_id),
            )
        else:
            conn.execute(
                "UPDATE purchase_orders SET status = 'partially_received' WHERE id = ?",
                (po_id,),
            )

    return get_purchase_order_by_id(conn, po_id)


def suggest_purchase_order_items(conn: sqlite3.Connection) -> list[POSuggestionItem]:
    sql = (
        "SELECT "
        "p.id AS product_id, "
        "p.sku, "
        "p.name, "
        "p.cost_paise, "
        "p.reorder_level, "
        "COALESCE(SUM(sm.qty_change), 0) AS current_stock "
        "FROM products p "
        "LEFT JOIN stock_movements sm ON p.id = sm.product_id "
        "WHERE p.active = 1 "
        "GROUP BY p.id "
        "HAVING current_stock <= p.reorder_level "
        "ORDER BY p.id ASC"
    )
    cursor = conn.execute(sql)
    suggestions: list[POSuggestionItem] = []
    for row in cursor.fetchall():
        c_stock = int(row["current_stock"])
        r_level = int(row["reorder_level"])
        suggested = max(r_level * 2 - c_stock, 1)
        suggestions.append(
            POSuggestionItem(
                product_id=int(row["product_id"]),
                sku=str(row["sku"]),
                name=str(row["name"]),
                current_stock=c_stock,
                reorder_level=r_level,
                suggested_qty=suggested,
                unit_cost_paise=int(row["cost_paise"]),
            )
        )
    return suggestions
