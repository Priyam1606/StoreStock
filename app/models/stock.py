from pydantic import BaseModel, Field


class StockLevelResponse(BaseModel):
    product_id: int
    sku: str
    name: str
    unit: str
    current_stock: int
    reorder_level: int


class StockMovementResponse(BaseModel):
    id: int
    product_id: int
    qty_change: int
    kind: str
    ref_type: str | None = None
    ref_id: int | None = None
    user_id: int
    note: str | None = None
    created_at: str


class StockAdjustmentCreate(BaseModel):
    product_id: int
    qty_change: int = Field(ge=-100000, le=100000)
    reason: str = Field(min_length=1)


class StockAdjustmentResponse(BaseModel):
    id: int
    product_id: int
    qty_change: int
    kind: str
    current_stock: int
    reason: str
    created_at: str
