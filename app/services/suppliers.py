import sqlite3
from datetime import datetime, timezone
from fastapi import HTTPException, status
from app.models.suppliers import SupplierCreate, SupplierUpdate, SupplierResponse


def create_supplier(conn: sqlite3.Connection, data: SupplierCreate) -> SupplierResponse:
    clean_name = data.name.strip()
    if not clean_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Supplier name cannot be empty",
        )
    clean_phone = data.phone.strip() if data.phone is not None and data.phone.strip() else None
    now_iso = datetime.now(timezone.utc).isoformat()
    cursor = conn.execute(
        "INSERT INTO suppliers (name, phone, active, created_at) VALUES (?, ?, 1, ?)",
        (clean_name, clean_phone, now_iso),
    )
    supplier_id = int(cursor.lastrowid)
    return SupplierResponse(
        id=supplier_id,
        name=clean_name,
        phone=clean_phone,
        active=True,
        created_at=now_iso,
    )


def get_supplier_by_id(conn: sqlite3.Connection, supplier_id: int) -> SupplierResponse:
    row = conn.execute(
        "SELECT id, name, phone, active, created_at FROM suppliers WHERE id = ?",
        (supplier_id,),
    ).fetchone()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found",
        )
    return SupplierResponse(
        id=int(row["id"]),
        name=str(row["name"]),
        phone=str(row["phone"]) if row["phone"] is not None else None,
        active=bool(row["active"]),
        created_at=str(row["created_at"]),
    )


def list_suppliers(
    conn: sqlite3.Connection,
    limit: int = 50,
    offset: int = 0,
) -> list[SupplierResponse]:
    limit = min(max(1, limit), 100)
    cursor = conn.execute(
        "SELECT id, name, phone, active, created_at FROM suppliers ORDER BY id ASC LIMIT ? OFFSET ?",
        (limit, offset),
    )
    return [
        SupplierResponse(
            id=int(row["id"]),
            name=str(row["name"]),
            phone=str(row["phone"]) if row["phone"] is not None else None,
            active=bool(row["active"]),
            created_at=str(row["created_at"]),
        )
        for row in cursor.fetchall()
    ]


def update_supplier(
    conn: sqlite3.Connection,
    supplier_id: int,
    data: SupplierUpdate,
) -> SupplierResponse:
    get_supplier_by_id(conn, supplier_id)

    fields: list[str] = []
    params: list[str | int] = []

    if data.name is not None:
        clean_name = data.name.strip()
        if not clean_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Supplier name cannot be empty",
            )
        fields.append("name = ?")
        params.append(clean_name)

    if data.phone is not None:
        clean_phone = data.phone.strip() if data.phone.strip() else None
        fields.append("phone = ?")
        params.append(clean_phone)

    if data.active is not None:
        fields.append("active = ?")
        params.append(1 if data.active else 0)

    if fields:
        params.append(supplier_id)
        conn.execute(f"UPDATE suppliers SET {', '.join(fields)} WHERE id = ?", params)

    return get_supplier_by_id(conn, supplier_id)
