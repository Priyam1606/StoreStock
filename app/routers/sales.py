import sqlite3
from fastapi import APIRouter, Depends, Query, status
from app.deps import get_db_conn, get_current_user
from app.models.sales import SaleCreate, SaleResponse, ReturnCreate, ReturnResponse
from app.models.users import UserInDB
from app.services.sales import (
    create_sale,
    get_sale_by_id,
    list_sales,
    create_return,
)

router = APIRouter()


@router.post("", response_model=SaleResponse, status_code=status.HTTP_201_CREATED)
def post_sale(
    data: SaleCreate,
    current_user: UserInDB = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db_conn),
) -> SaleResponse:
    return create_sale(conn, current_user.id, data)


@router.get("", response_model=list[SaleResponse])
def get_sales(
    date: str | None = None,
    customer_id: int | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: UserInDB = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db_conn),
) -> list[SaleResponse]:
    return list_sales(conn, date_str=date, customer_id=customer_id, limit=limit, offset=offset)


@router.get("/{sale_id}", response_model=SaleResponse)
def get_sale(
    sale_id: int,
    _: UserInDB = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db_conn),
) -> SaleResponse:
    return get_sale_by_id(conn, sale_id)


@router.post("/{sale_id}/returns", response_model=ReturnResponse, status_code=status.HTTP_201_CREATED)
def post_return(
    sale_id: int,
    data: ReturnCreate,
    current_user: UserInDB = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db_conn),
) -> ReturnResponse:
    return create_return(conn, current_user.id, sale_id, data)
