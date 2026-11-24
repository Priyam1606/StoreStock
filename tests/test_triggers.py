import sqlite3
import pytest
from app.db import get_connection


def create_base_records(conn: sqlite3.Connection) -> tuple[int, int, int]:
    user_cursor = conn.execute(
        "INSERT INTO users (username, password_hash, role, active, created_at) VALUES ('test_user', 'hash', 'owner', 1, '2026-01-01T00:00:00Z')",
    )
    user_id = int(user_cursor.lastrowid)

    prod_cursor = conn.execute(
        "INSERT INTO products (sku, name, unit, price_paise, cost_paise, reorder_level, active, created_at) VALUES ('SKU1', 'Item 1', 'pcs', 100, 50, 5, 1, '2026-01-01T00:00:00Z')",
    )
    product_id = int(prod_cursor.lastrowid)

    cust_cursor = conn.execute(
        "INSERT INTO customers (name, phone, credit_limit_paise, active, created_at) VALUES ('Cust 1', '9876543210', 1000, 1, '2026-01-01T00:00:00Z')",
    )
    customer_id = int(cust_cursor.lastrowid)

    return user_id, product_id, customer_id


def test_stock_movements_update_blocked(temp_db: str) -> None:
    conn = get_connection(temp_db)
    user_id, product_id, _ = create_base_records(conn)
    cursor = conn.execute(
        "INSERT INTO stock_movements (product_id, qty_change, kind, user_id, created_at) VALUES (?, 10, 'opening', ?, '2026-01-01T00:00:00Z')",
        (product_id, user_id),
    )
    movement_id = int(cursor.lastrowid)

    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        conn.execute("UPDATE stock_movements SET qty_change = 20 WHERE id = ?", (movement_id,))
    conn.close()


def test_stock_movements_delete_blocked(temp_db: str) -> None:
    conn = get_connection(temp_db)
    user_id, product_id, _ = create_base_records(conn)
    cursor = conn.execute(
        "INSERT INTO stock_movements (product_id, qty_change, kind, user_id, created_at) VALUES (?, 10, 'opening', ?, '2026-01-01T00:00:00Z')",
        (product_id, user_id),
    )
    movement_id = int(cursor.lastrowid)

    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        conn.execute("DELETE FROM stock_movements WHERE id = ?", (movement_id,))
    conn.close()


def test_credit_entries_update_blocked(temp_db: str) -> None:
    conn = get_connection(temp_db)
    user_id, _, customer_id = create_base_records(conn)
    cursor = conn.execute(
        "INSERT INTO credit_entries (customer_id, kind, amount_paise, user_id, created_at) VALUES (?, 'credit_sale', 500, ?, '2026-01-01T00:00:00Z')",
        (customer_id, user_id),
    )
    entry_id = int(cursor.lastrowid)

    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        conn.execute("UPDATE credit_entries SET amount_paise = 200 WHERE id = ?", (entry_id,))
    conn.close()


def test_credit_entries_delete_blocked(temp_db: str) -> None:
    conn = get_connection(temp_db)
    user_id, _, customer_id = create_base_records(conn)
    cursor = conn.execute(
        "INSERT INTO credit_entries (customer_id, kind, amount_paise, user_id, created_at) VALUES (?, 'credit_sale', 500, ?, '2026-01-01T00:00:00Z')",
        (customer_id, user_id),
    )
    entry_id = int(cursor.lastrowid)

    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        conn.execute("DELETE FROM credit_entries WHERE id = ?", (entry_id,))
    conn.close()


def test_audit_log_update_blocked(temp_db: str) -> None:
    conn = get_connection(temp_db)
    user_id, _, _ = create_base_records(conn)
    cursor = conn.execute(
        "INSERT INTO audit_log (user_id, action, entity_type, entity_id, created_at) VALUES (?, 'CREATE', 'product', 1, '2026-01-01T00:00:00Z')",
        (user_id,),
    )
    audit_id = int(cursor.lastrowid)

    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        conn.execute("UPDATE audit_log SET action = 'ALTER' WHERE id = ?", (audit_id,))
    conn.close()


def test_audit_log_delete_blocked(temp_db: str) -> None:
    conn = get_connection(temp_db)
    user_id, _, _ = create_base_records(conn)
    cursor = conn.execute(
        "INSERT INTO audit_log (user_id, action, entity_type, entity_id, created_at) VALUES (?, 'CREATE', 'product', 1, '2026-01-01T00:00:00Z')",
        (user_id,),
    )
    audit_id = int(cursor.lastrowid)

    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        conn.execute("DELETE FROM audit_log WHERE id = ?", (audit_id,))
    conn.close()
