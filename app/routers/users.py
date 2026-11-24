import sqlite3
from fastapi import APIRouter, Depends, status
from app.deps import get_db_conn, get_current_user, require_owner
from app.models.users import UserCreate, UserUpdate, UserResponse, UserInDB
from app.services.users import create_user, update_user_active

router = APIRouter()


@router.get("/me", response_model=UserResponse)
def get_me(current_user: UserInDB = Depends(get_current_user)) -> UserResponse:
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        active=current_user.active,
        created_at=current_user.created_at,
    )


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def post_user(
    user_data: UserCreate,
    _: UserInDB = Depends(require_owner),
    conn: sqlite3.Connection = Depends(get_db_conn),
) -> UserResponse:
    return create_user(conn, user_data)


@router.patch("/{user_id}", response_model=UserResponse)
def patch_user(
    user_id: int,
    update_data: UserUpdate,
    _: UserInDB = Depends(require_owner),
    conn: sqlite3.Connection = Depends(get_db_conn),
) -> UserResponse:
    return update_user_active(conn, user_id, update_data)
