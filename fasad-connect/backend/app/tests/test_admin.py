from __future__ import annotations


def test_admin_list_users(client, auth_headers):
    response = client.get("/api/v1/admin/users?page=1&size=20", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data
    assert data[0]["login"] == "admin"


def test_admin_create_user(client, auth_headers):
    roles_response = client.get("/api/v1/admin/roles?page=1&size=20", headers=auth_headers)
    role_id = roles_response.json()["data"][0]["id"]

    response = client.post(
        "/api/v1/admin/users",
        json={
            "full_name": "New Operator",
            "email": "operator@example.com",
            "login": "operator",
            "password": "operator123",
            "role_id": role_id,
            "is_active": True,
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["login"] == "operator"
    assert data["role"]["id"] == role_id
