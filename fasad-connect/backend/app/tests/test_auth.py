from __future__ import annotations


def test_auth_login(client):
    response = client.post("/api/v1/auth/login", json={"login": "admin", "password": "admin123"})

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["token"]["access_token"]
    assert payload["user"]["login"] == "admin"
