import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, Query, HTTPException, status
from app.deps import get_db_conn, get_current_user
from app.models.reports import (
    DailySummaryReport,
    TopSellingItem,
    CreditSummaryReport,
    InventoryValuationReport,
)
from app.models.users import UserInDB
from app.services.reports import (
    get_daily_summary,
    get_top_selling_products,
    get_credit_summary,
    get_inventory_valuation,
)

router = APIRouter()


@router.get("/daily-summary", response_model=DailySummaryReport)
def get_daily_summary_report(
    date: str | None = None,
    current_user: UserInDB = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db_conn),
) -> DailySummaryReport:
    if current_user.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner permission required",
        )
    if not date:
        date = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d")
    return get_daily_summary(conn, date)


@router.get("/top-selling", response_model=list[TopSellingItem])
def get_top_selling_report(
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = Query(default=10, ge=1, le=100),
    current_user: UserInDB = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db_conn),
) -> list[TopSellingItem]:
    if current_user.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner permission required",
        )
    return get_top_selling_products(conn, start_date=start_date, end_date=end_date, limit=limit)


@router.get("/credit-summary", response_model=CreditSummaryReport)
def get_credit_summary_report(
    current_user: UserInDB = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db_conn),
) -> CreditSummaryReport:
    if current_user.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner permission required",
        )
    return get_credit_summary(conn)


@router.get("/inventory-valuation", response_model=InventoryValuationReport)
def get_inventory_valuation_report(
    current_user: UserInDB = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db_conn),
) -> InventoryValuationReport:
    if current_user.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner permission required",
        )
    return get_inventory_valuation(conn)
