
from tests.test_monitors import create_monitor


def test_incidents_initially_empty(client):
    response = client.get("/api/v1/incidents")

    assert response.status_code == 200
    assert response.json() == []


def test_incident_status_filter_validation(client):
    response = client.get(
        "/api/v1/incidents",
        params={"status_filter": "invalid"},
    )

    assert response.status_code == 422


def test_incident_limit_validation(client):
    response = client.get(
        "/api/v1/incidents",
        params={"limit": 101},
    )

    assert response.status_code == 422


def test_missing_incident_returns_404(client):
    response = client.get("/api/v1/incidents/99999")

    assert response.status_code == 404
