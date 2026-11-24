import sqlite3
from fastapi import APIRouter, Depends, Query, status
from app.deps import get_db_conn, get_current_user
from app.models.customers import (
    CustomerCreate,
    CustomerUpdate,
    CustomerResponse,
    CustomerBalanceResponse,
    CreditEntryResponse,
    PaymentCreate,
)
from app.models.users import UserInDB
from app.services.customers import (
    create_customer,
    get_customer_by_id,
    list_customers,
    update_customer,
    get_customer_balance,
    get_customer_ledger,
    record_payment,
)

router = APIRouter()


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def post_customer(
    data: CustomerCreate,
    _: UserInDB = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db_conn),
) -> CustomerResponse:
    return create_customer(conn, data)


@router.get("", response_model=list[CustomerResponse])
def get_customers(
    q: str = "",
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: UserInDB = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db_conn),
) -> list[CustomerResponse]:
    return list_customers(conn, q=q, limit=limit, offset=offset)


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(
    customer_id: int,
    _: UserInDB = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db_conn),
) -> CustomerResponse:
    return get_customer_by_id(conn, customer_id)


@router.patch("/{customer_id}", response_model=CustomerResponse)
def patch_customer(
    customer_id: int,
    data: CustomerUpdate,
    current_user: UserInDB = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db_conn),
) -> CustomerResponse:
    return update_customer(conn, customer_id, current_user.role, data)


@router.get("/{customer_id}/balance", response_model=CustomerBalanceResponse)
def get_balance(
    customer_id: int,
    _: UserInDB = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db_conn),
) -> CustomerBalanceResponse:
    return get_customer_balance(conn, customer_id)


@router.get("/{customer_id}/ledger", response_model=list[CreditEntryResponse])
def get_ledger(
    customer_id: int,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: UserInDB = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db_conn),
) -> list[CreditEntryResponse]:
    return get_customer_ledger(conn, customer_id, limit=limit, offset=offset)


@router.post("/{customer_id}/payments", response_model=CreditEntryResponse, status_code=status.HTTP_201_CREATED)
def post_payment(
    customer_id: int,
    data: PaymentCreate,
    current_user: UserInDB = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db_conn),
) -> CreditEntryResponse:
    return record_payment(conn, customer_id, current_user.id, data)
