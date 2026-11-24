import sqlite3
from datetime import datetime, timezone
from fastapi import HTTPException, status
from app.db import transaction
from app.models.customers import (
    CustomerCreate,
    CustomerUpdate,
    CustomerResponse,
    CustomerBalanceResponse,
    CreditEntryResponse,
    PaymentCreate,
)


def create_customer(conn: sqlite3.Connection, data: CustomerCreate) -> CustomerResponse:
    name = data.name.strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Customer name cannot be empty",
        )

    phone = data.phone.strip() if data.phone is not None and data.phone.strip() else None
    if phone:
        existing = conn.execute("SELECT id FROM customers WHERE phone = ?", (phone,)).fetchone()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Phone number already registered to another customer",
            )

    now_iso = datetime.now(timezone.utc).isoformat()
    cursor = conn.execute(
        "INSERT INTO customers (name, phone, credit_limit_paise, active, created_at) VALUES (?, ?, ?, 1, ?)",
        (name, phone, data.credit_limit_paise, now_iso),
    )
    cust_id = int(cursor.lastrowid)
    return CustomerResponse(
        id=cust_id,
        name=name,
        phone=phone,
        credit_limit_paise=data.credit_limit_paise,
        active=True,
        created_at=now_iso,
    )


def get_customer_by_id(conn: sqlite3.Connection, customer_id: int) -> CustomerResponse:
    row = conn.execute(
        "SELECT id, name, phone, credit_limit_paise, active, created_at FROM customers WHERE id = ?",
        (customer_id,),
    ).fetchone()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )
    return CustomerResponse(
        id=int(row["id"]),
        name=str(row["name"]),
        phone=str(row["phone"]) if row["phone"] is not None else None,
        credit_limit_paise=int(row["credit_limit_paise"]),
        active=bool(row["active"]),
        created_at=str(row["created_at"]),
    )


def list_customers(
    conn: sqlite3.Connection,
    q: str = "",
    limit: int = 50,
    offset: int = 0,
) -> list[CustomerResponse]:
    limit = min(max(1, limit), 100)
    conditions: list[str] = []
    params: list[str | int] = []

    if q:
        escaped_q = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        search_term = f"%{escaped_q.lower()}%"
        conditions.append("(LOWER(name) LIKE ? ESCAPE '\\' OR LOWER(COALESCE(phone, '')) LIKE ? ESCAPE '\\')")
        params.extend([search_term, search_term])

    where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"SELECT id, name, phone, credit_limit_paise, active, created_at FROM customers{where_clause} ORDER BY id ASC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor = conn.execute(sql, params)
    return [
        CustomerResponse(
            id=int(row["id"]),
            name=str(row["name"]),
            phone=str(row["phone"]) if row["phone"] is not None else None,
            credit_limit_paise=int(row["credit_limit_paise"]),
            active=bool(row["active"]),
            created_at=str(row["created_at"]),
        )
        for row in cursor.fetchall()
    ]


def update_customer(
    conn: sqlite3.Connection,
    customer_id: int,
    user_role: str,
    data: CustomerUpdate,
) -> CustomerResponse:
    cust = conn.execute("SELECT id FROM customers WHERE id = ?", (customer_id,)).fetchone()
    if not cust:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )

    if (data.credit_limit_paise is not None or data.active is not None) and user_role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner permission required to update credit limit or active status",
        )

    fields: list[str] = []
    params: list[str | int] = []

    if data.name is not None:
        clean_name = data.name.strip()
        if not clean_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Customer name cannot be empty",
            )
        fields.append("name = ?")
        params.append(clean_name)

    if data.phone is not None:
        clean_phone = data.phone.strip() if data.phone.strip() else None
        if clean_phone:
            existing = conn.execute(
                "SELECT id FROM customers WHERE phone = ? AND id != ?",
                (clean_phone, customer_id),
            ).fetchone()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Phone number already registered to another customer",
                )
        fields.append("phone = ?")
        params.append(clean_phone)

    if data.credit_limit_paise is not None:
        fields.append("credit_limit_paise = ?")
        params.append(data.credit_limit_paise)

    if data.active is not None:
        fields.append("active = ?")
        params.append(1 if data.active else 0)

    if fields:
        params.append(customer_id)
        conn.execute(f"UPDATE customers SET {', '.join(fields)} WHERE id = ?", params)

    return get_customer_by_id(conn, customer_id)


def get_customer_balance(conn: sqlite3.Connection, customer_id: int) -> CustomerBalanceResponse:
    get_customer_by_id(conn, customer_id)
    cursor = conn.execute(
        "SELECT COALESCE(SUM(amount_paise), 0) AS balance FROM credit_entries WHERE customer_id = ?",
        (customer_id,),
    )
    balance = int(cursor.fetchone()["balance"])
    return CustomerBalanceResponse(customer_id=customer_id, balance_paise=balance)


def get_customer_ledger(
    conn: sqlite3.Connection,
    customer_id: int,
    limit: int = 50,
    offset: int = 0,
) -> list[CreditEntryResponse]:
    get_customer_by_id(conn, customer_id)
    limit = min(max(1, limit), 100)
    sql = (
        "SELECT id, customer_id, kind, amount_paise, sale_id, user_id, note, created_at "
        "FROM credit_entries "
        "WHERE customer_id = ? "
        "ORDER BY created_at DESC, id DESC "
        "LIMIT ? OFFSET ?"
    )
    cursor = conn.execute(sql, (customer_id, limit, offset))
    return [
        CreditEntryResponse(
            id=int(row["id"]),
            customer_id=int(row["customer_id"]),
            kind=str(row["kind"]),
            amount_paise=int(row["amount_paise"]),
            sale_id=int(row["sale_id"]) if row["sale_id"] is not None else None,
            user_id=int(row["user_id"]),
            note=str(row["note"]) if row["note"] is not None else None,
            created_at=str(row["created_at"]),
        )
        for row in cursor.fetchall()
    ]


def record_payment(
    conn: sqlite3.Connection,
    customer_id: int,
    user_id: int,
    data: PaymentCreate,
) -> CreditEntryResponse:
    with transaction(conn):
        cust_row = conn.execute(
            "SELECT id, active FROM customers WHERE id = ?",
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

        bal_row = conn.execute(
            "SELECT COALESCE(SUM(amount_paise), 0) AS current_balance FROM credit_entries WHERE customer_id = ?",
            (customer_id,),
        ).fetchone()
        current_balance = int(bal_row["current_balance"]) if bal_row else 0

        if data.amount_paise > current_balance:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Payment exceeds current balance",
            )

        now_iso = datetime.now(timezone.utc).isoformat()
        cursor = conn.execute(
            "INSERT INTO credit_entries (customer_id, kind, amount_paise, user_id, note, created_at) VALUES (?, 'payment', ?, ?, ?, ?)",
            (customer_id, -data.amount_paise, user_id, data.note, now_iso),
        )
        entry_id = int(cursor.lastrowid)

    return CreditEntryResponse(
        id=entry_id,
        customer_id=customer_id,
        kind="payment",
        amount_paise=-data.amount_paise,
        user_id=user_id,
        note=data.note,
        created_at=now_iso,
    )
