from typing import Literal
from pydantic import BaseModel


class UserCreate(BaseModel):
    username: str
    password: str
    role: Literal["owner", "staff"]


class UserUpdate(BaseModel):
    active: bool


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    active: bool
    created_at: str


class UserInDB(BaseModel):
    id: int
    username: str
    password_hash: str
    role: str
    active: bool
    created_at: str
