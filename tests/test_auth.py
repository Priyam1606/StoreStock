import hmac
from datetime import datetime, timezone, timedelta
import jwt
import pytest
from fastapi.testclient import TestClient
from app.config import get_settings
from app.db import get_connection
from app.security import hash_password, verify_password


def test_login_success(client: TestClient, owner_user: dict[str, str | int]) -> None:
    response = client.post(
        "/auth/login",
        json={"username": owner_user["username"], "password": owner_user["password"]},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

    token_alias_res = client.post(
        "/auth/token",
        json={"username": owner_user["username"], "password": owner_user["password"]},
    )
    assert token_alias_res.status_code == 200
    token_alias_data = token_alias_res.json()
    assert "access_token" in token_alias_data
    assert token_alias_data["token_type"] == "bearer"


def test_login_wrong_password(client: TestClient, owner_user: dict[str, str | int]) -> None:
    response = client.post(
        "/auth/login",
        json={"username": owner_user["username"], "password": "IncorrectPassword"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid credentials"}


def test_login_wrong_username(client: TestClient) -> None:
    response = client.post(
        "/auth/login",
        json={"username": "nonexistent_user", "password": "AnyPassword"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid credentials"}


def test_login_inactive_user(client: TestClient, staff_user: dict[str, str | int], temp_db: str) -> None:
    conn = get_connection(temp_db)
    conn.execute("UPDATE users SET active = 0 WHERE id = ?", (staff_user["id"],))
    conn.close()

    response = client.post(
        "/auth/login",
        json={"username": staff_user["username"], "password": staff_user["password"]},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "User is inactive"}


def test_invalid_token(client: TestClient) -> None:
    response = client.get(
        "/users/me",
        headers={"Authorization": "Bearer invalid.token.value"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid token"}


def test_expired_token(client: TestClient, owner_user: dict[str, str | int]) -> None:
    settings = get_settings()
    expired_time = datetime.now(timezone.utc) - timedelta(hours=1)
    payload = {
        "sub": str(owner_user["id"]),
        "username": owner_user["username"],
        "exp": expired_time,
    }
    expired_token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)

    response = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Token has expired"}


def test_deactivated_user_rejected_immediately(
    client: TestClient,
    staff_user: dict[str, str | int],
    staff_token: str,
    temp_db: str,
) -> None:
    headers = {"Authorization": f"Bearer {staff_token}"}
    response1 = client.get("/users/me", headers=headers)
    assert response1.status_code == 200
    assert response1.json()["username"] == staff_user["username"]

    conn = get_connection(temp_db)
    conn.execute("UPDATE users SET active = 0 WHERE id = ?", (staff_user["id"],))
    conn.close()

    response2 = client.get("/users/me", headers=headers)
    assert response2.status_code == 401
    assert response2.json() == {"detail": "User is inactive"}


def test_role_change_in_db_takes_effect_immediately(
    client: TestClient,
    staff_user: dict[str, str | int],
    staff_token: str,
    temp_db: str,
) -> None:
    headers = {"Authorization": f"Bearer {staff_token}"}
    create_payload = {
        "username": "new_staff_via_elevated",
        "password": "Password123",
        "role": "staff",
    }
    forbidden_response = client.post("/users", json=create_payload, headers=headers)
    assert forbidden_response.status_code == 403

    conn = get_connection(temp_db)
    conn.execute("UPDATE users SET role = 'owner' WHERE id = ?", (staff_user["id"],))
    conn.close()

    success_response = client.post("/users", json=create_payload, headers=headers)
    assert success_response.status_code == 201
    assert success_response.json()["username"] == "new_staff_via_elevated"


def test_nonexistent_user_token_rejected(client: TestClient) -> None:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(hours=1)
    payload = {
        "sub": "999999",
        "username": "ghost_user",
        "exp": expire,
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)

    response = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json() == {"detail": "User not found"}


def test_password_verification_with_compare_digest(monkeypatch: pytest.MonkeyPatch) -> None:
    digest_called = False
    original_compare_digest = hmac.compare_digest

    def mock_compare_digest(a: str, b: str) -> bool:
        nonlocal digest_called
        digest_called = True
        return original_compare_digest(a, b)

    monkeypatch.setattr("app.security.hmac.compare_digest", mock_compare_digest)

    hashed = hash_password("MySecurePass123")
    assert verify_password("MySecurePass123", hashed) is True
    assert digest_called is True

    digest_called = False
    assert verify_password("WrongPass", hashed) is False
    assert digest_called is True
    assert verify_password("MySecurePass123", "malformed$hash") is False

