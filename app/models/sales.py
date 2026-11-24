from typing import Literal
from pydantic import BaseModel, Field


class SaleItemCreate(BaseModel):
    product_id: int
    qty: int = Field(gt=0, le=100000)


class SaleCreate(BaseModel):
    payment_type: Literal["cash", "credit"]
    customer_id: int | None = None
    items: list[SaleItemCreate] = Field(min_length=1)


class SaleItemResponse(BaseModel):
    id: int
    sale_id: int
    product_id: int
    qty: int
    unit_price_paise: int
    line_total_paise: int


class SaleResponse(BaseModel):
    id: int
    customer_id: int | None = None
    user_id: int
    payment_type: str
    total_paise: int
    created_at: str
    items: list[SaleItemResponse]


class ReturnItemCreate(BaseModel):
    sale_item_id: int
    qty: int = Field(gt=0, le=100000)


class ReturnCreate(BaseModel):
    items: list[ReturnItemCreate] = Field(min_length=1)


class ReturnItemResponse(BaseModel):
    id: int
    return_id: int
    sale_item_id: int
    qty: int


class ReturnResponse(BaseModel):
    id: int
    sale_id: int
    user_id: int
    refund_paise: int
    created_at: str
    items: list[ReturnItemResponse]
