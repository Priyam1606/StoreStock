from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    sku: str
    name: str
    unit: str
    price_paise: int = Field(ge=0, le=10**12)
    cost_paise: int = Field(ge=0, le=10**12)
    reorder_level: int = Field(default=0, ge=0, le=100000)


class ProductUpdate(BaseModel):
    name: str | None = None
    unit: str | None = None
    price_paise: int | None = Field(default=None, ge=0, le=10**12)
    cost_paise: int | None = Field(default=None, ge=0, le=10**12)
    reorder_level: int | None = Field(default=None, ge=0, le=100000)
    active: bool | None = None


class ProductResponse(BaseModel):
    id: int
    sku: str
    name: str
    unit: str
    price_paise: int
    cost_paise: int
    reorder_level: int
    active: bool
    created_at: str


class ProductStaffResponse(BaseModel):
    id: int
    sku: str
    name: str
    unit: str
    price_paise: int
    reorder_level: int
    active: bool
    created_at: str


class ProductImportResponse(BaseModel):
    imported: int
