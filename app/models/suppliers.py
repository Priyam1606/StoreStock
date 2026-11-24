from pydantic import BaseModel, Field


class SupplierCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=50)


class SupplierUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    active: bool | None = None


class SupplierResponse(BaseModel):
    id: int
    name: str
    phone: str | None = None
    active: bool
    created_at: str
