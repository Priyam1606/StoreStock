import sqlite3
from fastapi import APIRouter, Depends
from app.deps import get_db_conn
from app.models.auth import LoginRequest, TokenResponse
from app.services.auth import authenticate_user

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
@router.post("/token", response_model=TokenResponse)
def login(request: LoginRequest, conn: sqlite3.Connection = Depends(get_db_conn)) -> TokenResponse:
    return authenticate_user(conn, request)
