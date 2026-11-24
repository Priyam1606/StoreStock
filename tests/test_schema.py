import sqlite3
import subprocess
import sys
import pytest
from app.db import get_connection


def test_all_thirteen_tables_exist(temp_db: str) -> None:
    conn = get_connection(temp_db)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'",
    )
    tables = {row["name"] for row in cursor.fetchall()}
    conn.close()

    expected_tables = {
        "users",
        "products",
        "stock_movements",
        "customers",
        "sales",
        "sale_items",
        "returns",
        "return_items",
        "credit_entries",
        "suppliers",
        "purchase_orders",
        "purchase_order_items",
        "audit_log",
    }
    assert expected_tables.issubset(tables)
    assert len(expected_tables) == 13


def test_stock_levels_view_exists(temp_db: str) -> None:
    conn = get_connection(temp_db)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='view' AND name='stock_levels'",
    )
    row = cursor.fetchone()
    assert row is not None

    user_cur = conn.execute(
        "INSERT INTO users (username, password_hash, role, active, created_at) VALUES ('view_user', 'h', 'staff', 1, '2026-01-01T00:00:00Z')",
    )
    user_id = int(user_cur.lastrowid)

    prod_cur = conn.execute(
        "INSERT INTO products (sku, name, unit, price_paise, cost_paise, reorder_level, active, created_at) VALUES ('VIEW_SKU', 'View Product', 'pcs', 100, 80, 5, 1, '2026-01-01T00:00:00Z')",
    )
    prod_id = int(prod_cur.lastrowid)

    view_before = conn.execute(
        "SELECT current_stock FROM stock_levels WHERE product_id = ?",
        (prod_id,),
    ).fetchone()
    assert view_before["current_stock"] == 0

    conn.execute(
        "INSERT INTO stock_movements (product_id, qty_change, kind, user_id, created_at) VALUES (?, 15, 'opening', ?, '2026-01-01T00:00:00Z')",
        (prod_id, user_id),
    )
    conn.execute(
        "INSERT INTO stock_movements (product_id, qty_change, kind, user_id, created_at) VALUES (?, -3, 'sale', ?, '2026-01-01T00:00:00Z')",
        (prod_id, user_id),
    )

    view_after = conn.execute(
        "SELECT current_stock FROM stock_levels WHERE product_id = ?",
        (prod_id,),
    ).fetchone()
    assert view_after["current_stock"] == 12
    conn.close()


def test_credit_sale_without_customer_rejected(temp_db: str) -> None:
    conn = get_connection(temp_db)
    user_cur = conn.execute(
        "INSERT INTO users (username, password_hash, role, active, created_at) VALUES ('sale_user', 'h', 'staff', 1, '2026-01-01T00:00:00Z')",
    )
    user_id = int(user_cur.lastrowid)

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO sales (customer_id, user_id, payment_type, total_paise, created_at) VALUES (NULL, ?, 'credit', 500, '2026-01-01T00:00:00Z')",
            (user_id,),
        )
    conn.close()


def test_create_owner_cli_script(temp_db: str) -> None:
    python_binary = sys.executable
    result = subprocess.run(
        [python_binary, "-m", "scripts.create_owner", "--username", "cli_admin", "--password", "AdminPass123"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Owner cli_admin created successfully" in result.stdout

    conn = get_connection(temp_db)
    row = conn.execute("SELECT id, role, active FROM users WHERE username = 'cli_admin'").fetchone()
    conn.close()
    assert row is not None
    assert row["role"] == "owner"
    assert row["active"] == 1

    duplicate_result = subprocess.run(
        [python_binary, "-m", "scripts.create_owner", "--username", "cli_admin", "--password", "AdminPass123"],
        capture_output=True,
        text=True,
    )
    assert duplicate_result.returncode != 0
    assert "User already exists" in duplicate_result.stderr


def test_seed_script(tmp_path) -> None:
    seed_db = str(tmp_path / "seed_test.db")
    import os
    env = os.environ.copy()
    env["STORESTOCK_DB_PATH"] = seed_db

    python_binary = sys.executable
    result = subprocess.run(
        [python_binary, "-m", "scripts.seed"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0
    assert "Database seeded successfully!" in result.stdout
    assert "username='owner'" in result.stdout
    assert "username='staff'" in result.stdout

    conn = get_connection(seed_db)
    prod_count = conn.execute("SELECT COUNT(*) AS c FROM products").fetchone()["c"]
    sup_count = conn.execute("SELECT COUNT(*) AS c FROM suppliers").fetchone()["c"]
    cust_count = conn.execute("SELECT COUNT(*) AS c FROM customers").fetchone()["c"]
    po_sent = conn.execute("SELECT COUNT(*) AS c FROM purchase_orders WHERE status = 'sent'").fetchone()["c"]

    assert prod_count == 60
    assert sup_count == 3
    assert cust_count == 8
    assert po_sent == 1

    po_received = conn.execute("SELECT COUNT(*) AS c FROM purchase_orders WHERE status = 'received'").fetchone()["c"]
    po_partial = conn.execute("SELECT COUNT(*) AS c FROM purchase_orders WHERE status = 'partially_received'").fetchone()["c"]
    po_draft = conn.execute("SELECT COUNT(*) AS c FROM purchase_orders WHERE status = 'draft'").fetchone()["c"]
    assert po_received == 1
    assert po_partial == 1
    assert po_draft == 1

    low_stock = conn.execute("SELECT COUNT(*) AS c FROM stock_levels sl JOIN products p ON sl.product_id = p.id WHERE sl.current_stock < p.reorder_level").fetchone()["c"]
    zero_stock = conn.execute("SELECT COUNT(*) AS c FROM stock_levels WHERE current_stock == 0").fetchone()["c"]
    boundary_stock = conn.execute("SELECT COUNT(*) AS c FROM stock_levels sl JOIN products p ON sl.product_id = p.id WHERE sl.current_stock == p.reorder_level").fetchone()["c"]
    healthy_stock = conn.execute("SELECT COUNT(*) AS c FROM stock_levels sl JOIN products p ON sl.product_id = p.id WHERE sl.current_stock > p.reorder_level").fetchone()["c"]
    conn.close()

    assert low_stock == 8
    assert zero_stock == 2
    assert boundary_stock == 2
    assert healthy_stock == 50

    second_run = subprocess.run(
        [python_binary, "-m", "scripts.seed"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert second_run.returncode != 0
    assert "refusing to seed" in second_run.stderr


def test_seed_refuses_when_products_non_empty(temp_db: str) -> None:
    conn = get_connection(temp_db)
    conn.execute(
        "INSERT INTO products (sku, name, unit, price_paise, cost_paise, reorder_level, active, created_at) VALUES ('NON_EMPTY_SKU', 'Non Empty Test', 'pcs', 100, 50, 5, 1, '2026-01-01T00:00:00Z')",
    )
    conn.close()

    import os
    env = os.environ.copy()
    env["STORESTOCK_DB_PATH"] = temp_db

    python_binary = sys.executable
    result = subprocess.run(
        [python_binary, "-m", "scripts.seed"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode != 0
    assert "refusing to seed" in result.stderr


