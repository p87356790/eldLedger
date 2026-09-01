from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint_reports_ok() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "eldledger-backend"
    assert payload["database"] == "connected"


def test_root_health_alias() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_hello_world() -> None:
    response = client.get("/api/hello")
    assert response.status_code == 200
    payload = response.json()
    assert payload["message"] == "Hello World"
    assert payload["app"] == "eldLedger"
