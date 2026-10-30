from fastapi.testclient import TestClient

from stock_monitor.application import create_app


def test_login_and_access_dashboard():
    with TestClient(create_app()) as client:
        response = client.get("/")
        assert response.status_code == 200

        login_response = client.post(
            "/login",
            data={"username": "admin", "password": "admin"},
            follow_redirects=False,
        )
        assert login_response.status_code == 303

        dashboard_response = client.get("/dashboard")
        assert dashboard_response.status_code == 200
        assert "Мониторинг акций" in dashboard_response.text


def test_start_monitoring_returns_mock_state_without_token():
    with TestClient(create_app()) as client:
        client.post("/login", data={"username": "admin", "password": "admin"})

        response = client.post(
            "/api/start",
            json={
                "tickers": ["SBER", "GAZP"],
                "change_percent": "2",
                "window_minutes": 5,
                "rollback_percent": "33.33",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is True
        assert payload["state"]["mode"] == "mock"
        assert len(payload["state"]["rows"]) == 2
