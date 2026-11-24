from pydantic import BaseModel


class DailySummaryReport(BaseModel):
    date: str
    total_sales_paise: int
    total_cash_sales_paise: int
    total_credit_sales_paise: int
    total_returns_paise: int
    net_sales_paise: int
    total_cost_paise: int
    gross_profit_paise: int
    sales_count: int
    returns_count: int


class TopSellingItem(BaseModel):
    product_id: int
    sku: str
    name: str
    qty_sold: int
    total_revenue_paise: int


class CustomerCreditSummaryItem(BaseModel):
    customer_id: int
    name: str
    phone: str | None = None
    balance_paise: int
    credit_limit_paise: int


class CreditSummaryReport(BaseModel):
    total_outstanding_paise: int
    total_credit_limit_paise: int
    customers_with_balance_count: int
    customers: list[CustomerCreditSummaryItem]


class InventoryValuationReport(BaseModel):
    total_items: int
    total_cost_paise: int
    total_retail_paise: int
    potential_profit_paise: int
