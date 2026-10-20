
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base
from app.main import app
from app.models import Incident, Monitor
from app.routers import incidents, monitors


@pytest.fixture()
def client():
    # An isolated in-memory SQLite database for tests only.
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    TestingSessionLocal = sessionmaker(
        bind=test_engine,
        autoflush=False,
        expire_on_commit=False,
    )

    Base.metadata.create_all(bind=test_engine)

    def override_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    # Each router has its own database dependency.
    app.dependency_overrides[monitors.get_db] = override_db
    app.dependency_overrides[incidents.get_db] = override_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()


def create_monitor(client):
    response = client.post(
        "/api/v1/monitors",
        json={
            "name": "Test Website",
            "url": "https://example.com",
            "interval_seconds": 60,
            "timeout_seconds": 10,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_create_monitor(client):
    monitor = create_monitor(client)

    assert monitor["name"] == "Test Website"
    assert monitor["url"] == "https://example.com/"
    assert monitor["is_active"] is True
    assert monitor["id"] > 0


def test_list_monitors(client):
    create_monitor(client)

    response = client.get("/api/v1/monitors")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["name"] == "Test Website"


def test_get_monitor(client):
    monitor = create_monitor(client)

    response = client.get(f"/api/v1/monitors/{monitor['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == monitor["id"]


def test_get_missing_monitor_returns_404(client):
    response = client.get("/api/v1/monitors/99999")

    assert response.status_code == 404


def test_update_monitor(client):
    monitor = create_monitor(client)

    response = client.patch(
        f"/api/v1/monitors/{monitor['id']}",
        json={"name": "Updated Website", "is_active": False},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Updated Website"
    assert response.json()["is_active"] is False


def test_delete_monitor(client):
    monitor = create_monitor(client)

    response = client.delete(f"/api/v1/monitors/{monitor['id']}")

    assert response.status_code == 204

    follow_up = client.get(f"/api/v1/monitors/{monitor['id']}")
    assert follow_up.status_code == 404


def test_create_monitor_rejects_invalid_interval(client):
    response = client.post(
        "/api/v1/monitors",
        json={
            "name": "Invalid Monitor",
            "url": "https://example.com",
            "interval_seconds": 10,
            "timeout_seconds": 5,
        },
    )

    assert response.status_code == 422


def test_list_incidents(client):
    monitor_data = create_monitor(client)

    # Seed an incident directly; no real website check is performed.
    db_override = app.dependency_overrides[incidents.get_db]
    db_generator = db_override()
    db = next(db_generator)

    try:
        db.add(
            Incident(
                monitor_id=monitor_data["id"],
                status="open",
                description="Test incident",
            )
        )
        db.commit()
    finally:
        db_generator.close()

    response = client.get("/api/v1/incidents")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["status"] == "open"
    assert response.json()[0]["monitor_name"] == "Test Website"


def test_filter_open_incidents(client):
    monitor_data = create_monitor(client)

    db_generator = app.dependency_overrides[incidents.get_db]()
    db = next(db_generator)

    try:
        db.add_all(
            [
                Incident(
                    monitor_id=monitor_data["id"],
                    status="open",
                    description="Open test incident",
                ),
                Incident(
                    monitor_id=monitor_data["id"],
                    status="resolved",
                    description="Resolved test incident",
                ),
            ]
        )
        db.commit()
    finally:
        db_generator.close()

    response = client.get(
        "/api/v1/incidents",
        params={"status_filter": "open"},
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["status"] == "open"


def test_invalid_incident_filter_returns_422(client):
    response = client.get(
        "/api/v1/incidents",
        params={"status_filter": "unknown"},
    )

    assert response.status_code == 422


def test_incident_limit_above_100_returns_422(client):
    response = client.get(
        "/api/v1/incidents",
        params={"limit": 101},
    )

    assert response.status_code == 422


def test_missing_incident_returns_404(client):
    response = client.get("/api/v1/incidents/99999")

    assert response.status_code == 404
