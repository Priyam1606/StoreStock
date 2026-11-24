import os
from pathlib import Path
from typing import Generator
import pytest
from fastapi.testclient import TestClient
from app.config import get_settings
from app.db import init_db, get_connection
from app.security import hash_password, create_access_token
from app.main import app

os.environ["STORESTOCK_SECRET"] = "test-secret-key-storestock-phase1-validation"


@pytest.fixture
def temp_db(tmp_path: Path) -> Generator[str, None, None]:
    db_file = tmp_path / "test.db"
    db_path = str(db_file)
    os.environ["STORESTOCK_DB_PATH"] = db_path
    init_db(db_path)
    yield db_path


@pytest.fixture
def client(temp_db: str) -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def owner_user(temp_db: str) -> dict[str, str | int]:
    conn = get_connection(temp_db)
    password_hash = hash_password("OwnerPass123")
    cursor = conn.execute(
        "INSERT INTO users (username, password_hash, role, active, created_at) VALUES (?, ?, 'owner', 1, '2026-01-01T00:00:00Z')",
        ("test_owner", password_hash),
    )
    user_id = int(cursor.lastrowid)
    conn.close()
    return {"id": user_id, "username": "test_owner", "password": "OwnerPass123", "role": "owner"}


@pytest.fixture
def staff_user(temp_db: str) -> dict[str, str | int]:
    conn = get_connection(temp_db)
    password_hash = hash_password("StaffPass123")
    cursor = conn.execute(
        "INSERT INTO users (username, password_hash, role, active, created_at) VALUES (?, ?, 'staff', 1, '2026-01-01T00:00:00Z')",
        ("test_staff", password_hash),
    )
    user_id = int(cursor.lastrowid)
    conn.close()
    return {"id": user_id, "username": "test_staff", "password": "StaffPass123", "role": "staff"}


@pytest.fixture
def owner_token(owner_user: dict[str, str | int]) -> str:
    return create_access_token(user_id=int(owner_user["id"]), username=str(owner_user["username"]))


@pytest.fixture
def staff_token(staff_user: dict[str, str | int]) -> str:
    return create_access_token(user_id=int(staff_user["id"]), username=str(staff_user["username"]))


@pytest.fixture
def owner_headers(owner_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {owner_token}"}


@pytest.fixture
def staff_headers(staff_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {staff_token}"}
