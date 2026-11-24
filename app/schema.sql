CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('owner', 'staff')),
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0, 1)),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name TEXT NOT NULL,
    unit TEXT NOT NULL,
    price_paise INTEGER NOT NULL CHECK(price_paise >= 0),
    cost_paise INTEGER NOT NULL CHECK(cost_paise >= 0),
    reorder_level INTEGER NOT NULL DEFAULT 0 CHECK(reorder_level >= 0),
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0, 1)),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stock_movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id),
    qty_change INTEGER NOT NULL CHECK(qty_change != 0),
    kind TEXT NOT NULL CHECK(kind IN ('opening', 'sale', 'delivery', 'return', 'adjustment')),
    ref_type TEXT,
    ref_id INTEGER,
    user_id INTEGER NOT NULL REFERENCES users(id),
    note TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT UNIQUE,
    credit_limit_paise INTEGER NOT NULL DEFAULT 0 CHECK(credit_limit_paise >= 0),
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0, 1)),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER REFERENCES customers(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    payment_type TEXT NOT NULL CHECK(payment_type IN ('cash', 'credit')),
    total_paise INTEGER NOT NULL CHECK(total_paise >= 0),
    created_at TEXT NOT NULL,
    CHECK(payment_type != 'credit' OR customer_id IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS sale_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL REFERENCES sales(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    qty INTEGER NOT NULL CHECK(qty > 0),
    unit_price_paise INTEGER NOT NULL CHECK(unit_price_paise >= 0),
    unit_cost_paise INTEGER NOT NULL CHECK(unit_cost_paise >= 0),
    line_total_paise INTEGER NOT NULL CHECK(line_total_paise >= 0)
);

CREATE TABLE IF NOT EXISTS returns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL REFERENCES sales(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    refund_paise INTEGER NOT NULL CHECK(refund_paise >= 0),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS return_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    return_id INTEGER NOT NULL REFERENCES returns(id),
    sale_item_id INTEGER NOT NULL REFERENCES sale_items(id),
    qty INTEGER NOT NULL CHECK(qty > 0)
);

CREATE TABLE IF NOT EXISTS credit_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    kind TEXT NOT NULL CHECK(kind IN ('credit_sale', 'payment', 'return', 'adjustment')),
    amount_paise INTEGER NOT NULL CHECK(amount_paise != 0),
    sale_id INTEGER REFERENCES sales(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    note TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT,
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0, 1)),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS purchase_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
    status TEXT NOT NULL CHECK(status IN ('draft', 'sent', 'partially_received', 'received', 'cancelled')),
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    sent_at TEXT,
    received_at TEXT
);

CREATE TABLE IF NOT EXISTS purchase_order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_order_id INTEGER NOT NULL REFERENCES purchase_orders(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    qty_ordered INTEGER NOT NULL CHECK(qty_ordered > 0),
    qty_received INTEGER NOT NULL DEFAULT 0 CHECK(qty_received >= 0 AND qty_received <= qty_ordered),
    unit_cost_paise INTEGER NOT NULL CHECK(unit_cost_paise >= 0)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    old_value TEXT,
    new_value TEXT,
    created_at TEXT NOT NULL
);

CREATE VIEW IF NOT EXISTS stock_levels AS
SELECT
    p.id AS product_id,
    p.sku,
    p.name,
    COALESCE(SUM(sm.qty_change), 0) AS current_stock
FROM products p
LEFT JOIN stock_movements sm ON p.id = sm.product_id
GROUP BY p.id;

CREATE TRIGGER IF NOT EXISTS trg_stock_movements_no_update
BEFORE UPDATE ON stock_movements
BEGIN
    SELECT RAISE(ABORT, 'stock_movements table is append-only');
END;

CREATE TRIGGER IF NOT EXISTS trg_stock_movements_no_delete
BEFORE DELETE ON stock_movements
BEGIN
    SELECT RAISE(ABORT, 'stock_movements table is append-only');
END;

CREATE TRIGGER IF NOT EXISTS trg_credit_entries_no_update
BEFORE UPDATE ON credit_entries
BEGIN
    SELECT RAISE(ABORT, 'credit_entries table is append-only');
END;

CREATE TRIGGER IF NOT EXISTS trg_credit_entries_no_delete
BEFORE DELETE ON credit_entries
BEGIN
    SELECT RAISE(ABORT, 'credit_entries table is append-only');
END;

CREATE TRIGGER IF NOT EXISTS trg_audit_log_no_update
BEFORE UPDATE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'audit_log table is append-only');
END;

CREATE TRIGGER IF NOT EXISTS trg_audit_log_no_delete
BEFORE DELETE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'audit_log table is append-only');
END;

CREATE INDEX IF NOT EXISTS idx_stock_movements_product_created ON stock_movements(product_id, created_at);
CREATE INDEX IF NOT EXISTS idx_sales_customer_id ON sales(customer_id);
CREATE INDEX IF NOT EXISTS idx_sales_created_at ON sales(created_at);
CREATE INDEX IF NOT EXISTS idx_sale_items_sale_id ON sale_items(sale_id);
CREATE INDEX IF NOT EXISTS idx_sale_items_product_id ON sale_items(product_id);
CREATE INDEX IF NOT EXISTS idx_returns_sale_id ON returns(sale_id);
CREATE INDEX IF NOT EXISTS idx_return_items_sale_item_id ON return_items(sale_item_id);
CREATE INDEX IF NOT EXISTS idx_credit_entries_customer_id ON credit_entries(customer_id);
CREATE INDEX IF NOT EXISTS idx_purchase_order_items_po_id ON purchase_order_items(purchase_order_id);
