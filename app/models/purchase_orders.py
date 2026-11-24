from pydantic import BaseModel, Field


class POItemCreate(BaseModel):
    product_id: int
    qty_ordered: int = Field(gt=0, le=100000)
    unit_cost_paise: int = Field(ge=0, le=10**12)


class POCreate(BaseModel):
    supplier_id: int
    items: list[POItemCreate] = Field(min_length=1, max_length=200)


class POReceiveItem(BaseModel):
    item_id: int | None = None
    product_id: int | None = None
    qty: int


class POReceiveRequest(BaseModel):
    items: list[POReceiveItem] = Field(min_length=1, max_length=200)


class POItemResponse(BaseModel):
    id: int
    purchase_order_id: int
    product_id: int
    qty_ordered: int
    qty_received: int
    unit_cost_paise: int


class POItemStaffResponse(BaseModel):
    id: int
    purchase_order_id: int
    product_id: int
    qty_ordered: int
    qty_received: int


class POResponse(BaseModel):
    id: int
    supplier_id: int
    status: str
    created_by: int
    created_at: str
    sent_at: str | None = None
    received_at: str | None = None
    items: list[POItemResponse]


class POStaffResponse(BaseModel):
    id: int
    supplier_id: int
    status: str
    created_by: int
    created_at: str
    sent_at: str | None = None
    received_at: str | None = None
    items: list[POItemStaffResponse]


class POSuggestionItem(BaseModel):
    product_id: int
    sku: str
    name: str
    current_stock: int
    reorder_level: int
    suggested_qty: int
    unit_cost_paise: int


class POSuggestionStaffItem(BaseModel):
    product_id: int
    sku: str
    name: str
    current_stock: int
    reorder_level: int
    suggested_qty: int
