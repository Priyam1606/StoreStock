import sqlite3
from fastapi import APIRouter, Depends, File, UploadFile, status, HTTPException, Query
from app.deps import get_db_conn, get_current_user, require_owner
from app.models.products import (
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    ProductStaffResponse,
    ProductImportResponse,
)
from app.models.stock import StockMovementResponse
from app.models.users import UserInDB
from app.services.products import (
    create_product,
    get_product_by_id,
    list_products,
    update_product,
    import_products_csv,
)
from app.services.stock import get_product_movements

router = APIRouter()


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def post_product(
    data: ProductCreate,
    _: UserInDB = Depends(require_owner),
    conn: sqlite3.Connection = Depends(get_db_conn),
) -> ProductResponse:
    return create_product(conn, data)


@router.get("")
def get_products(
    q: str = "",
    active: bool | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: UserInDB = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db_conn),
) -> list[ProductResponse] | list[ProductStaffResponse]:
    products = list_products(conn, q=q, active=active, limit=limit, offset=offset)
    if current_user.role == "staff":
        return [ProductStaffResponse(**p) for p in products]
    return [ProductResponse(**p) for p in products]


@router.get("/{product_id}")
def get_product(
    product_id: int,
    current_user: UserInDB = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db_conn),
) -> ProductResponse | ProductStaffResponse:
    product = get_product_by_id(conn, product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    if current_user.role == "staff":
        return ProductStaffResponse(**product)
    return ProductResponse(**product)


@router.get("/{product_id}/movements", response_model=list[StockMovementResponse])
def get_movements(
    product_id: int,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: UserInDB = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db_conn),
) -> list[StockMovementResponse]:
    return get_product_movements(conn, product_id, limit=limit, offset=offset)


@router.patch("/{product_id}", response_model=ProductResponse)
def patch_product(
    product_id: int,
    data: ProductUpdate,
    current_user: UserInDB = Depends(require_owner),
    conn: sqlite3.Connection = Depends(get_db_conn),
) -> ProductResponse:
    return update_product(conn, product_id, current_user.id, data)


@router.post("/import", response_model=ProductImportResponse)
def post_import_products(
    file: UploadFile = File(...),
    current_user: UserInDB = Depends(require_owner),
    conn: sqlite3.Connection = Depends(get_db_conn),
) -> ProductImportResponse:
    raw_bytes = file.file.read()
    if len(raw_bytes) > 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="CSV upload exceeds 1 MB limit",
        )
    content = raw_bytes.decode("utf-8-sig")
    return import_products_csv(conn, current_user.id, content)
