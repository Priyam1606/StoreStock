from pydantic import BaseModel, Field


class CustomerCreate(BaseModel):
    name: str = Field(min_length=1)
    phone: str | None = None
    credit_limit_paise: int = Field(default=0, ge=0, le=10**12)


class CustomerUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    credit_limit_paise: int | None = Field(default=None, ge=0, le=10**12)
    active: bool | None = None


class CustomerResponse(BaseModel):
    id: int
    name: str
    phone: str | None = None
    credit_limit_paise: int
    active: bool
    created_at: str


class CustomerBalanceResponse(BaseModel):
    customer_id: int
    balance_paise: int


class CreditEntryResponse(BaseModel):
    id: int
    customer_id: int
    kind: str
    amount_paise: int
    sale_id: int | None = None
    user_id: int
    note: str | None = None
    created_at: str


class PaymentCreate(BaseModel):
    amount_paise: int = Field(gt=0, le=10**12)
    note: str | None = None
