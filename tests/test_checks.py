
from datetime import datetime, timedelta, timezone

from app.models import CheckResult

from tests.test_monitors import create_monitor


def add_check(
    session_factory,
    monitor_id,
    checked_at,
    status="up",
    status_code=200,
):
    db = session_factory()
    try:
        result = CheckResult(
            monitor_id=monitor_id,
            status=status,
            status_code=status_code,
            response_time_ms=100,
            checked_at=checked_at,
        )
        db.add(result)
        db.commit()
        db.refresh(result)
        return result.id
    finally:
        db.close()


def test_check_history_returns_results(client):
    monitor_id = create_monitor(client).json()["id"]
    session_factory = client.app.state.TestingSessionLocal

    now = datetime.now(timezone.utc)

    add_check(
        session_factory,
        monitor_id,
        now - timedelta(minutes=2),
    )
    add_check(
        session_factory,
        monitor_id,
        now - timedelta(minutes=1),
    )

    response = client.get(
        f"/api/v1/monitors/{monitor_id}/checks",
        params={"limit": 50},
    )

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_check_history_limit_one_returns_one_result(client):
    monitor_id = create_monitor(client).json()["id"]
    session_factory = client.app.state.TestingSessionLocal

    now = datetime.now(timezone.utc)

    add_check(session_factory, monitor_id, now - timedelta(minutes=2))
    add_check(session_factory, monitor_id, now - timedelta(minutes=1))

    response = client.get(
        f"/api/v1/monitors/{monitor_id}/checks",
        params={"limit": 1},
    )

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_check_history_rejects_limit_above_100(client):
    monitor_id = create_monitor(client).json()["id"]

    response = client.get(
        f"/api/v1/monitors/{monitor_id}/checks",
        params={"limit": 101},
    )

    assert response.status_code == 422


def test_check_history_rejects_limit_below_one(client):
    monitor_id = create_monitor(client).json()["id"]

    response = client.get(
        f"/api/v1/monitors/{monitor_id}/checks",
        params={"limit": 0},
    )

    assert response.status_code == 422


def test_check_history_missing_monitor_returns_404(client):
    response = client.get("/api/v1/monitors/99999/checks")

    assert response.status_code == 404
