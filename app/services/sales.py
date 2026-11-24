import sqlite3
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from fastapi import HTTPException, status
from app.db import transaction
from app.models.sales import (
    SaleCreate,
    SaleItemCreate,
    SaleResponse,
    SaleItemResponse,
    ReturnCreate,
    ReturnResponse,
    ReturnItemResponse,
)


def get_kolkata_day_bounds(date_str: str) -> tuple[str, str]:
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format, expected YYYY-MM-DD",
        )
    kolkata_tz = ZoneInfo("Asia/Kolkata")
    start_local = dt.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=kolkata_tz)
    end_local = start_local + timedelta(days=1)
    start_utc = start_local.astimezone(timezone.utc).isoformat()
    end_utc = end_local.astimezone(timezone.utc).isoformat()
    return start_utc, end_utc


def validate_sale_request(data: SaleCreate) -> None:
    if not data.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sale must contain at least one item",
        )
    if len(data.items) > 200:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sale cannot contain more than 200 items",
        )
    product_ids = [item.product_id for item in data.items]
    if len(product_ids) != len(set(product_ids)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Duplicate product lines in sale",
        )
    for item in data.items:
        if item.qty <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Item quantity must be greater than zero",
            )
    if data.payment_type == "credit" and data.customer_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Customer is required for credit sale",
        )


def load_and_check_lines(
    conn: sqlite3.Connection,
    items: list[SaleItemCreate],
) -> tuple[list[dict[str, int]], int]:
    item_details: list[dict[str, int]] = []
    total_paise = 0

    for item in items:
        prod_row = conn.execute(
            "SELECT id, name, price_paise, cost_paise, active FROM products WHERE id = ?",
            (item.product_id,),
        ).fetchone()
        if not prod_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product {item.product_id} not found",
            )
        if not bool(prod_row["active"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Product {prod_row['name']} is inactive",
            )

        stock_row = conn.execute(
            "SELECT COALESCE(SUM(qty_change), 0) AS current_stock FROM stock_movements WHERE product_id = ?",
            (item.product_id,),
        ).fetchone()
        avail = int(stock_row["current_stock"]) if stock_row else 0
        if avail < item.qty:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Insufficient stock for product {prod_row['name']}: requested {item.qty}, available {avail}",
            )

        unit_price = int(prod_row["price_paise"])
        unit_cost = int(prod_row["cost_paise"])
        line_total = item.qty * unit_price
        total_paise += line_total
        item_details.append(
            {
                "product_id": item.product_id,
                "qty": item.qty,
                "unit_price_paise": unit_price,
                "unit_cost_paise": unit_cost,
                "line_total_paise": line_total,
            }
        )

    if total_paise > 10**12:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sale total exceeds limit of 10^12 paise",
        )

    return item_details, total_paise


def check_credit(
    conn: sqlite3.Connection,
    customer_id: int | None,
    payment_type: str,
    total_paise: int,
) -> None:
    if customer_id is not None:
        cust_row = conn.execute(
            "SELECT id, credit_limit_paise, active FROM customers WHERE id = ?",
            (customer_id,),
        ).fetchone()
        if not cust_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found",
            )
        if not bool(cust_row["active"]):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Customer is inactive",
            )

        if payment_type == "credit":
            bal_row = conn.execute(
                "SELECT COALESCE(SUM(amount_paise), 0) AS current_balance FROM credit_entries WHERE customer_id = ?",
                (customer_id,),
            ).fetchone()
            current_balance = int(bal_row["current_balance"]) if bal_row else 0
            credit_limit = int(cust_row["credit_limit_paise"])

            if current_balance + total_paise > credit_limit:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Credit limit exceeded",
                )


def write_sale(
    conn: sqlite3.Connection,
    user_id: int,
    customer_id: int | None,
    payment_type: str,
    total_paise: int,
    item_details: list[dict[str, int]],
    now_iso: str,
) -> tuple[int, list[SaleItemResponse]]:
    cursor = conn.execute(
        "INSERT INTO sales (customer_id, user_id, payment_type, total_paise, created_at) VALUES (?, ?, ?, ?, ?)",
        (customer_id, user_id, payment_type, total_paise, now_iso),
    )
    sale_id = int(cursor.lastrowid)

    saved_items: list[SaleItemResponse] = []
    for det in item_details:
        cur_item = conn.execute(
            "INSERT INTO sale_items (sale_id, product_id, qty, unit_price_paise, unit_cost_paise, line_total_paise) VALUES (?, ?, ?, ?, ?, ?)",
            (sale_id, det["product_id"], det["qty"], det["unit_price_paise"], det["unit_cost_paise"], det["line_total_paise"]),
        )
        item_id = int(cur_item.lastrowid)
        conn.execute(
            "INSERT INTO stock_movements (product_id, qty_change, kind, ref_type, ref_id, user_id, note, created_at) VALUES (?, ?, 'sale', 'sale', ?, ?, 'Sale', ?)",
            (det["product_id"], -det["qty"], sale_id, user_id, now_iso),
        )
        saved_items.append(
            SaleItemResponse(
                id=item_id,
                sale_id=sale_id,
                product_id=det["product_id"],
                qty=det["qty"],
                unit_price_paise=det["unit_price_paise"],
                line_total_paise=det["line_total_paise"],
            )
        )

    if payment_type == "credit":
        conn.execute(
            "INSERT INTO credit_entries (customer_id, kind, amount_paise, sale_id, user_id, note, created_at) VALUES (?, 'credit_sale', ?, ?, ?, 'Credit sale', ?)",
            (customer_id, total_paise, sale_id, user_id, now_iso),
        )

    return sale_id, saved_items


def create_sale(conn: sqlite3.Connection, user_id: int, data: SaleCreate) -> SaleResponse:
    validate_sale_request(data)

    with transaction(conn):
        item_details, total_paise = load_and_check_lines(conn, data.items)
        check_credit(conn, data.customer_id, data.payment_type, total_paise)
        now_iso = datetime.now(timezone.utc).isoformat()
        sale_id, saved_items = write_sale(
            conn, user_id, data.customer_id, data.payment_type, total_paise, item_details, now_iso
        )

    return SaleResponse(
        id=sale_id,
        customer_id=data.customer_id,
        user_id=user_id,
        payment_type=data.payment_type,
        total_paise=total_paise,
        created_at=now_iso,
        items=saved_items,
    )


def get_sale_by_id(conn: sqlite3.Connection, sale_id: int) -> SaleResponse:
    sale_row = conn.execute(
        "SELECT id, customer_id, user_id, payment_type, total_paise, created_at FROM sales WHERE id = ?",
        (sale_id,),
    ).fetchone()
    if not sale_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sale not found",
        )

    items_cursor = conn.execute(
        "SELECT id, sale_id, product_id, qty, unit_price_paise, line_total_paise FROM sale_items WHERE sale_id = ? ORDER BY id ASC",
        (sale_id,),
    )
    items = [
        SaleItemResponse(
            id=int(row["id"]),
            sale_id=int(row["sale_id"]),
            product_id=int(row["product_id"]),
            qty=int(row["qty"]),
            unit_price_paise=int(row["unit_price_paise"]),
            line_total_paise=int(row["line_total_paise"]),
        )
        for row in items_cursor.fetchall()
    ]

    return SaleResponse(
        id=int(sale_row["id"]),
        customer_id=int(sale_row["customer_id"]) if sale_row["customer_id"] is not None else None,
        user_id=int(sale_row["user_id"]),
        payment_type=str(sale_row["payment_type"]),
        total_paise=int(sale_row["total_paise"]),
        created_at=str(sale_row["created_at"]),
        items=items,
    )


def list_sales(
    conn: sqlite3.Connection,
    date_str: str | None = None,
    customer_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[SaleResponse]:
    limit = min(max(1, limit), 100)
    conditions: list[str] = []
    params: list[str | int] = []

    if date_str:
        start_utc, end_utc = get_kolkata_day_bounds(date_str)
        conditions.append("created_at >= ? AND created_at < ?")
        params.extend([start_utc, end_utc])

    if customer_id is not None:
        conditions.append("customer_id = ?")
        params.append(customer_id)

    where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"SELECT id FROM sales{where_clause} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor = conn.execute(sql, params)
    sale_ids = [int(row["id"]) for row in cursor.fetchall()]
    return [get_sale_by_id(conn, sid) for sid in sale_ids]


def create_return(
    conn: sqlite3.Connection,
    user_id: int,
    sale_id: int,
    data: ReturnCreate,
) -> ReturnResponse:
    if not data.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Return must contain at least one item",
        )

    item_ids = [item.sale_item_id for item in data.items]
    if len(item_ids) != len(set(item_ids)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Duplicate sale item lines in return",
        )

    with transaction(conn):
        sale = conn.execute(
            "SELECT id, customer_id, payment_type FROM sales WHERE id = ?",
            (sale_id,),
        ).fetchone()
        if not sale:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sale not found",
            )

        total_refund_paise = 0
        return_plan: list[dict[str, int]] = []

        for item in data.items:
            if item.qty <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Return quantity must be greater than zero",
                )

            line = conn.execute(
                "SELECT id, product_id, qty, unit_price_paise FROM sale_items WHERE id = ? AND sale_id = ?",
                (item.sale_item_id, sale_id),
            ).fetchone()
            if not line:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Sale item {item.sale_item_id} not found in this sale",
                )

            ret_sum_row = conn.execute(
                "SELECT COALESCE(SUM(qty), 0) AS returned_qty FROM return_items WHERE sale_item_id = ?",
                (item.sale_item_id,),
            ).fetchone()
            already_returned = int(ret_sum_row["returned_qty"]) if ret_sum_row else 0
            sold_qty = int(line["qty"])
            remaining = sold_qty - already_returned

            if item.qty > remaining:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Cannot return {item.qty} units; only {remaining} available to return for item {item.sale_item_id}",
                )

            unit_price = int(line["unit_price_paise"])
            line_refund = item.qty * unit_price
            total_refund_paise += line_refund
            return_plan.append(
                {
                    "sale_item_id": item.sale_item_id,
                    "product_id": int(line["product_id"]),
                    "qty": item.qty,
                }
            )

        now_iso = datetime.now(timezone.utc).isoformat()
        cursor = conn.execute(
            "INSERT INTO returns (sale_id, user_id, refund_paise, created_at) VALUES (?, ?, ?, ?)",
            (sale_id, user_id, total_refund_paise, now_iso),
        )
        return_id = int(cursor.lastrowid)

        saved_return_items: list[ReturnItemResponse] = []
        for plan in return_plan:
            cur_item = conn.execute(
                "INSERT INTO return_items (return_id, sale_item_id, qty) VALUES (?, ?, ?)",
                (return_id, plan["sale_item_id"], plan["qty"]),
            )
            ret_item_id = int(cur_item.lastrowid)
            conn.execute(
                "INSERT INTO stock_movements (product_id, qty_change, kind, ref_type, ref_id, user_id, note, created_at) VALUES (?, ?, 'return', 'return', ?, ?, 'Sale return', ?)",
                (plan["product_id"], plan["qty"], return_id, user_id, now_iso),
            )
            saved_return_items.append(
                ReturnItemResponse(
                    id=ret_item_id,
                    return_id=return_id,
                    sale_item_id=plan["sale_item_id"],
                    qty=plan["qty"],
                )
            )

        if str(sale["payment_type"]) == "credit" and sale["customer_id"] is not None:
            conn.execute(
                "INSERT INTO credit_entries (customer_id, kind, amount_paise, sale_id, user_id, note, created_at) VALUES (?, 'return', ?, ?, ?, 'Return credit', ?)",
                (int(sale["customer_id"]), -total_refund_paise, sale_id, user_id, now_iso),
            )

    return ReturnResponse(
        id=return_id,
        sale_id=sale_id,
        user_id=user_id,
        refund_paise=total_refund_paise,
        created_at=now_iso,
        items=saved_return_items,
    )
