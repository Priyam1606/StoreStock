import sqlite3
from fastapi import APIRouter, Depends, Query, HTTPException, status
from app.deps import get_db_conn, get_current_user
from app.models.purchase_orders import (
    POCreate,
    POResponse,
    POStaffResponse,
    POItemStaffResponse,
    POReceiveRequest,
    POSuggestionItem,
    POSuggestionStaffItem,
)
from app.models.users import UserInDB
from app.services.purchase_orders import (
    create_purchase_order,
    get_purchase_order_by_id,
    list_purchase_orders,
    send_purchase_order,
    cancel_purchase_order,
    receive_purchase_order_items,
    suggest_purchase_order_items,
)

router = APIRouter()


@router.post("", response_model=POResponse, status_code=status.HTTP_201_CREATED)
def post_purchase_order(
    data: POCreate,
    current_user: UserInDB = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db_conn),
) -> POResponse:
    if current_user.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner permission required",
        )
    return create_purchase_order(conn, current_user.id, data)


@router.post("/suggest")
@router.get("/suggest")
def get_or_post_po_suggestions(
    current_user: UserInDB = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db_conn),
) -> list[POSuggestionItem] | list[POSuggestionStaffItem]:
    suggestions = suggest_purchase_order_items(conn)
    if current_user.role == "staff":
        return [
            POSuggestionStaffItem(
                product_id=s.product_id,
                sku=s.sku,
                name=s.name,
                current_stock=s.current_stock,
                reorder_level=s.reorder_level,
                suggested_qty=s.suggested_qty,
            )
            for s in suggestions
        ]
    return suggestions


def to_staff_response(po: POResponse) -> POStaffResponse:
    return POStaffResponse(
        id=po.id,
        supplier_id=po.supplier_id,
        status=po.status,
        created_by=po.created_by,
        created_at=po.created_at,
        sent_at=po.sent_at,
        received_at=po.received_at,
        items=[
            POItemStaffResponse(
                id=it.id,
                purchase_order_id=it.purchase_order_id,
                product_id=it.product_id,
                qty_ordered=it.qty_ordered,
                qty_received=it.qty_received,
            )
            for it in po.items
        ],
    )


@router.get("")
def get_purchase_orders(
    status_filter: str | None = Query(default=None, alias="status"),
    supplier_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: UserInDB = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db_conn),
) -> list[POResponse] | list[POStaffResponse]:
    pos = list_purchase_orders(
        conn,
        status_filter=status_filter,
        supplier_id=supplier_id,
        limit=limit,
        offset=offset,
    )
    if current_user.role == "staff":
        return [to_staff_response(po) for po in pos]
    return pos


@router.get("/{po_id}")
def get_single_purchase_order(
    po_id: int,
    current_user: UserInDB = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db_conn),
) -> POResponse | POStaffResponse:
    po = get_purchase_order_by_id(conn, po_id)
    if current_user.role == "staff":
        return to_staff_response(po)
    return po


@router.post("/{po_id}/send", response_model=POResponse)
def post_send_purchase_order(
    po_id: int,
    current_user: UserInDB = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db_conn),
) -> POResponse:
    if current_user.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner permission required",
        )
    return send_purchase_order(conn, po_id)


@router.post("/{po_id}/cancel", response_model=POResponse)
def post_cancel_purchase_order(
    po_id: int,
    current_user: UserInDB = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db_conn),
) -> POResponse:
    if current_user.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner permission required",
        )
    return cancel_purchase_order(conn, po_id)


@router.post("/{po_id}/receive")
def post_receive_purchase_order(
    po_id: int,
    data: POReceiveRequest,
    current_user: UserInDB = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db_conn),
) -> POResponse | POStaffResponse:
    po = receive_purchase_order_items(conn, current_user.id, po_id, data)
    if current_user.role == "staff":
        return to_staff_response(po)
    return po
