from fastapi.testclient import TestClient


def test_get_me_owner(client: TestClient, owner_headers: dict[str, str], owner_user: dict[str, str | int]) -> None:
    response = client.get("/users/me", headers=owner_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == owner_user["id"]
    assert data["username"] == owner_user["username"]
    assert data["role"] == "owner"
    assert data["active"] is True
    assert "created_at" in data


def test_get_me_staff(client: TestClient, staff_headers: dict[str, str], staff_user: dict[str, str | int]) -> None:
    response = client.get("/users/me", headers=staff_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == staff_user["id"]
    assert data["username"] == staff_user["username"]
    assert data["role"] == "staff"


def test_get_me_unauthenticated(client: TestClient) -> None:
    response = client.get("/users/me")
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_owner_create_staff(client: TestClient, owner_headers: dict[str, str]) -> None:
    payload = {
        "username": "new_staff_member",
        "password": "Password123",
        "role": "staff",
    }
    response = client.post("/users", json=payload, headers=owner_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "new_staff_member"
    assert data["role"] == "staff"
    assert data["active"] is True


def test_owner_create_owner(client: TestClient, owner_headers: dict[str, str]) -> None:
    payload = {
        "username": "new_owner_member",
        "password": "Password123",
        "role": "owner",
    }
    response = client.post("/users", json=payload, headers=owner_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "new_owner_member"
    assert data["role"] == "owner"


def test_create_user_duplicate_username(
    client: TestClient,
    owner_headers: dict[str, str],
    owner_user: dict[str, str | int],
) -> None:
    payload = {
        "username": owner_user["username"],
        "password": "Password123",
        "role": "staff",
    }
    response = client.post("/users", json=payload, headers=owner_headers)
    assert response.status_code == 409
    assert response.json() == {"detail": "Username already exists"}


def test_staff_cannot_create_user(client: TestClient, staff_headers: dict[str, str]) -> None:
    payload = {
        "username": "staff_attempt",
        "password": "Password123",
        "role": "staff",
    }
    response = client.post("/users", json=payload, headers=staff_headers)
    assert response.status_code == 403
    assert response.json() == {"detail": "Owner permission required"}


def test_owner_patch_user_active(
    client: TestClient,
    owner_headers: dict[str, str],
    staff_user: dict[str, str | int],
) -> None:
    response = client.patch(
        f"/users/{staff_user['id']}",
        json={"active": False},
        headers=owner_headers,
    )
    assert response.status_code == 200
    assert response.json()["active"] is False

    reactivate = client.patch(
        f"/users/{staff_user['id']}",
        json={"active": True},
        headers=owner_headers,
    )
    assert reactivate.status_code == 200
    assert reactivate.json()["active"] is True


def test_staff_cannot_patch_user(
    client: TestClient,
    staff_headers: dict[str, str],
    owner_user: dict[str, str | int],
) -> None:
    response = client.patch(
        f"/users/{owner_user['id']}",
        json={"active": False},
        headers=staff_headers,
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "Owner permission required"}


def test_patch_nonexistent_user(client: TestClient, owner_headers: dict[str, str]) -> None:
    response = client.patch(
        "/users/99999",
        json={"active": False},
        headers=owner_headers,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "User not found"}
