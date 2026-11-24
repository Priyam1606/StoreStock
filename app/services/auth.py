import sqlite3
from fastapi import HTTPException, status
from app.models.auth import LoginRequest, TokenResponse
from app.security import verify_password, create_access_token


def authenticate_user(conn: sqlite3.Connection, request: LoginRequest) -> TokenResponse:
    cursor = conn.execute(
        "SELECT id, username, password_hash, role, active, created_at FROM users WHERE username = ?",
        (request.username,),
    )
    row = cursor.fetchone()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    if not verify_password(request.password, row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    if not bool(row["active"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is inactive",
        )
    token = create_access_token(user_id=int(row["id"]), username=str(row["username"]))
    return TokenResponse(access_token=token, token_type="bearer")
