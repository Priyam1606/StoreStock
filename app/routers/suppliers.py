import sqlite3
from fastapi import APIRouter, Depends, Query, HTTPException, status
from app.deps import get_db_conn, get_current_user
from app.models.suppliers import SupplierCreate, SupplierUpdate, SupplierResponse
from app.models.users import UserInDB
from app.services.suppliers import (
    create_supplier,
    get_supplier_by_id,
    list_suppliers,
    update_supplier,
)

router = APIRouter()


@router.post("", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED)
def post_supplier(
    data: SupplierCreate,
    current_user: UserInDB = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db_conn),
) -> SupplierResponse:
    if current_user.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner permission required",
        )
    return create_supplier(conn, data)


@router.get("", response_model=list[SupplierResponse])
def get_suppliers(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: UserInDB = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db_conn),
) -> list[SupplierResponse]:
    return list_suppliers(conn, limit=limit, offset=offset)


@router.get("/{supplier_id}", response_model=SupplierResponse)
def get_supplier(
    supplier_id: int,
    _: UserInDB = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db_conn),
) -> SupplierResponse:
    return get_supplier_by_id(conn, supplier_id)


@router.patch("/{supplier_id}", response_model=SupplierResponse)
def patch_supplier(
    supplier_id: int,
    data: SupplierUpdate,
    current_user: UserInDB = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db_conn),
) -> SupplierResponse:
    if current_user.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner permission required",
        )
    return update_supplier(conn, supplier_id, data)
