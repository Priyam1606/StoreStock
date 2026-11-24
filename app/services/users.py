import sqlite3
from datetime import datetime, timezone
from fastapi import HTTPException, status
from app.models.users import UserCreate, UserResponse, UserInDB, UserUpdate
from app.security import hash_password


def get_user_by_id(conn: sqlite3.Connection, user_id: int) -> UserInDB | None:
    cursor = conn.execute(
        "SELECT id, username, password_hash, role, active, created_at FROM users WHERE id = ?",
        (user_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    return UserInDB(
        id=int(row["id"]),
        username=str(row["username"]),
        password_hash=str(row["password_hash"]),
        role=str(row["role"]),
        active=bool(row["active"]),
        created_at=str(row["created_at"]),
    )


def get_user_by_username(conn: sqlite3.Connection, username: str) -> UserInDB | None:
    cursor = conn.execute(
        "SELECT id, username, password_hash, role, active, created_at FROM users WHERE username = ?",
        (username,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    return UserInDB(
        id=int(row["id"]),
        username=str(row["username"]),
        password_hash=str(row["password_hash"]),
        role=str(row["role"]),
        active=bool(row["active"]),
        created_at=str(row["created_at"]),
    )


def create_user(conn: sqlite3.Connection, user_data: UserCreate) -> UserResponse:
    existing = get_user_by_username(conn, user_data.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )
    hashed_password = hash_password(user_data.password)
    created_at = datetime.now(timezone.utc).isoformat()
    cursor = conn.execute(
        "INSERT INTO users (username, password_hash, role, active, created_at) VALUES (?, ?, ?, 1, ?)",
        (user_data.username, hashed_password, user_data.role, created_at),
    )
    new_id = int(cursor.lastrowid)
    return UserResponse(
        id=new_id,
        username=user_data.username,
        role=user_data.role,
        active=True,
        created_at=created_at,
    )


def update_user_active(conn: sqlite3.Connection, user_id: int, update_data: UserUpdate) -> UserResponse:
    user = get_user_by_id(conn, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    conn.execute(
        "UPDATE users SET active = ? WHERE id = ?",
        (1 if update_data.active else 0, user_id),
    )
    return UserResponse(
        id=user.id,
        username=user.username,
        role=user.role,
        active=update_data.active,
        created_at=user.created_at,
    )
