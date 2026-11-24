import sqlite3
from app.services.sales import get_kolkata_day_bounds
from app.models.reports import (
    DailySummaryReport,
    TopSellingItem,
    CustomerCreditSummaryItem,
    CreditSummaryReport,
    InventoryValuationReport,
)


def get_daily_summary(conn: sqlite3.Connection, date_str: str) -> DailySummaryReport:
    start_utc, end_utc = get_kolkata_day_bounds(date_str)

    sales_row = conn.execute(
        "SELECT "
        "COUNT(*) AS sales_count, "
        "COALESCE(SUM(total_paise), 0) AS total_sales_paise, "
        "COALESCE(SUM(CASE WHEN payment_type = 'cash' THEN total_paise ELSE 0 END), 0) AS total_cash_sales_paise, "
        "COALESCE(SUM(CASE WHEN payment_type = 'credit' THEN total_paise ELSE 0 END), 0) AS total_credit_sales_paise "
        "FROM sales WHERE created_at >= ? AND created_at < ?",
        (start_utc, end_utc),
    ).fetchone()

    sold_cost_row = conn.execute(
        "SELECT COALESCE(SUM(si.qty * si.unit_cost_paise), 0) AS sold_cost "
        "FROM sale_items si "
        "JOIN sales s ON si.sale_id = s.id "
        "WHERE s.created_at >= ? AND s.created_at < ?",
        (start_utc, end_utc),
    ).fetchone()

    returns_row = conn.execute(
        "SELECT "
        "COUNT(*) AS returns_count, "
        "COALESCE(SUM(refund_paise), 0) AS total_returns_paise "
        "FROM returns WHERE created_at >= ? AND created_at < ?",
        (start_utc, end_utc),
    ).fetchone()

    returned_cost_row = conn.execute(
        "SELECT COALESCE(SUM(ri.qty * si.unit_cost_paise), 0) AS returned_cost "
        "FROM return_items ri "
        "JOIN returns r ON ri.return_id = r.id "
        "JOIN sale_items si ON ri.sale_item_id = si.id "
        "WHERE r.created_at >= ? AND r.created_at < ?",
        (start_utc, end_utc),
    ).fetchone()

    total_sales = int(sales_row["total_sales_paise"])
    total_cash = int(sales_row["total_cash_sales_paise"])
    total_credit = int(sales_row["total_credit_sales_paise"])
    sales_cnt = int(sales_row["sales_count"])

    total_returns = int(returns_row["total_returns_paise"])
    returns_cnt = int(returns_row["returns_count"])

    sold_cost = int(sold_cost_row["sold_cost"])
    returned_cost = int(returned_cost_row["returned_cost"])

    net_sales = total_sales - total_returns
    net_cost = sold_cost - returned_cost
    gross_profit = net_sales - net_cost

    return DailySummaryReport(
        date=date_str,
        total_sales_paise=total_sales,
        total_cash_sales_paise=total_cash,
        total_credit_sales_paise=total_credit,
        total_returns_paise=total_returns,
        net_sales_paise=net_sales,
        total_cost_paise=net_cost,
        gross_profit_paise=gross_profit,
        sales_count=sales_cnt,
        returns_count=returns_cnt,
    )


def get_top_selling_products(
    conn: sqlite3.Connection,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 10,
) -> list[TopSellingItem]:
    limit = min(max(1, limit), 100)
    conditions: list[str] = []
    params: list[str | int] = []

    if start_date:
        start_utc, _ = get_kolkata_day_bounds(start_date)
        conditions.append("s.created_at >= ?")
        params.append(start_utc)

    if end_date:
        _, end_utc = get_kolkata_day_bounds(end_date)
        conditions.append("s.created_at < ?")
        params.append(end_utc)

    where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = (
        "SELECT "
        "p.id AS product_id, "
        "p.sku, "
        "p.name, "
        "COALESCE(SUM(si.qty), 0) AS qty_sold, "
        "COALESCE(SUM(si.line_total_paise), 0) AS total_revenue_paise "
        "FROM products p "
        "JOIN sale_items si ON p.id = si.product_id "
        f"JOIN sales s ON si.sale_id = s.id{where_clause} "
        "GROUP BY p.id "
        "ORDER BY qty_sold DESC, total_revenue_paise DESC "
        "LIMIT ?"
    )
    params.append(limit)

    cursor = conn.execute(sql, params)
    return [
        TopSellingItem(
            product_id=int(row["product_id"]),
            sku=str(row["sku"]),
            name=str(row["name"]),
            qty_sold=int(row["qty_sold"]),
            total_revenue_paise=int(row["total_revenue_paise"]),
        )
        for row in cursor.fetchall()
    ]


def get_credit_summary(conn: sqlite3.Connection) -> CreditSummaryReport:
    cursor = conn.execute(
        "SELECT "
        "c.id AS customer_id, "
        "c.name, "
        "c.phone, "
        "c.credit_limit_paise, "
        "COALESCE(SUM(ce.amount_paise), 0) AS balance_paise "
        "FROM customers c "
        "LEFT JOIN credit_entries ce ON c.id = ce.customer_id "
        "GROUP BY c.id "
        "HAVING balance_paise > 0 "
        "ORDER BY balance_paise DESC",
    )
    customers = [
        CustomerCreditSummaryItem(
            customer_id=int(row["customer_id"]),
            name=str(row["name"]),
            phone=str(row["phone"]) if row["phone"] is not None else None,
            balance_paise=int(row["balance_paise"]),
            credit_limit_paise=int(row["credit_limit_paise"]),
        )
        for row in cursor.fetchall()
    ]

    tot_limit_row = conn.execute(
        "SELECT COALESCE(SUM(credit_limit_paise), 0) AS tot FROM customers WHERE active = 1",
    ).fetchone()
    total_credit_limit = int(tot_limit_row["tot"]) if tot_limit_row else 0
    total_outstanding = sum(item.balance_paise for item in customers)

    return CreditSummaryReport(
        total_outstanding_paise=total_outstanding,
        total_credit_limit_paise=total_credit_limit,
        customers_with_balance_count=len(customers),
        customers=customers,
    )


def get_inventory_valuation(conn: sqlite3.Connection) -> InventoryValuationReport:
    sql = (
        "SELECT "
        "COALESCE(SUM(sl.current_stock), 0) AS total_items, "
        "COALESCE(SUM(CASE WHEN sl.current_stock > 0 THEN sl.current_stock * p.cost_paise ELSE 0 END), 0) AS total_cost_paise, "
        "COALESCE(SUM(CASE WHEN sl.current_stock > 0 THEN sl.current_stock * p.price_paise ELSE 0 END), 0) AS total_retail_paise "
        "FROM stock_levels sl "
        "JOIN products p ON sl.product_id = p.id"
    )
    row = conn.execute(sql).fetchone()
    total_items = int(row["total_items"]) if row else 0
    total_cost = int(row["total_cost_paise"]) if row else 0
    total_retail = int(row["total_retail_paise"]) if row else 0
    potential_profit = total_retail - total_cost

    return InventoryValuationReport(
        total_items=total_items,
        total_cost_paise=total_cost,
        total_retail_paise=total_retail,
        potential_profit_paise=potential_profit,
    )
