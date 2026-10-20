
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint_returns_success():
    response = client.get("/health/live")

    assert response.status_code == 200


def test_dashboard_page_loads():
    response = client.get("/dashboard")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_dashboard_stylesheet_is_available():
    response = client.get("/static/dashboard.css")

    assert response.status_code == 200
