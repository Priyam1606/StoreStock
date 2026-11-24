import sqlite3
from fastapi import APIRouter, Depends, status
from app.deps import get_db_conn, get_current_user, require_owner
from app.models.stock import (
    StockLevelResponse,
    StockAdjustmentCreate,
    StockAdjustmentResponse,
)
from app.models.users import UserInDB
from app.services.stock import (
    get_stock_levels,
    get_low_stock,
    create_adjustment,
)

router = APIRouter()


@router.get("", response_model=list[StockLevelResponse])
def get_all_stock(
    _: UserInDB = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db_conn),
) -> list[StockLevelResponse]:
    return get_stock_levels(conn)


@router.get("/low", response_model=list[StockLevelResponse])
def get_low_stock_products(
    _: UserInDB = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db_conn),
) -> list[StockLevelResponse]:
    return get_low_stock(conn)


@router.post("/adjustments", response_model=StockAdjustmentResponse, status_code=status.HTTP_201_CREATED)
def post_stock_adjustment(
    data: StockAdjustmentCreate,
    current_user: UserInDB = Depends(require_owner),
    conn: sqlite3.Connection = Depends(get_db_conn),
) -> StockAdjustmentResponse:
    return create_adjustment(conn, current_user.id, data)
