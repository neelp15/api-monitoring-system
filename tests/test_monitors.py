
def create_monitor(client, name="Test Website", url="https://example.com"):
    return client.post(
        "/api/v1/monitors",
        json={
            "name": name,
            "url": url,
            "interval_seconds": 60,
            "timeout_seconds": 10,
        },
    )


def test_create_monitor(client):
    response = create_monitor(client)

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Website"
    assert data["url"] == "https://example.com/"
    assert data["interval_seconds"] == 60
    assert data["is_active"] is True
    assert "id" in data


def test_list_monitors(client):
    create_monitor(client, name="Website One")
    create_monitor(client, name="Website Two")

    response = client.get("/api/v1/monitors")

    assert response.status_code == 200
    names = [monitor["name"] for monitor in response.json()]
    assert len(names) == 2
    assert "Website One" in names
    assert "Website Two" in names


def test_get_monitor(client):
    created = create_monitor(client).json()

    response = client.get(f"/api/v1/monitors/{created['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_update_monitor(client):
    created = create_monitor(client).json()

    response = client.patch(
        f"/api/v1/monitors/{created['id']}",
        json={"name": "Updated Website", "is_active": False},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Updated Website"
    assert response.json()["is_active"] is False


def test_delete_monitor(client):
    created = create_monitor(client)

    monitor_id = created.json()["id"]
    response = client.delete(f"/api/v1/monitors/{monitor_id}")

    assert response.status_code == 204
    assert client.get(f"/api/v1/monitors/{monitor_id}").status_code == 404


def test_create_monitor_rejects_invalid_interval(client):
    response = client.post(
        "/api/v1/monitors",
        json={
            "name": "Invalid Monitor",
            "url": "https://example.com",
            "interval_seconds": 10,
            "timeout_seconds": 10,
        },
    )

    assert response.status_code == 422


def test_get_missing_monitor_returns_404(client):
    response = client.get("/api/v1/monitors/99999")

    assert response.status_code == 404


def test_create_monitor_rejects_invalid_url(client):
    response = client.post(
        "/api/v1/monitors",
        json={
            "name": "Invalid URL Monitor",
            "url": "not-a-valid-url",
            "interval_seconds": 60,
            "timeout_seconds": 10,
        },
    )

    assert response.status_code == 422


def test_create_monitor_rejects_unsupported_url_scheme(client):
    response = client.post(
        "/api/v1/monitors",
        json={
            "name": "FTP Monitor",
            "url": "ftp://example.com",
            "interval_seconds": 60,
            "timeout_seconds": 10,
        },
    )

    assert response.status_code == 422


def test_create_monitor_rejects_missing_name(client):
    response = client.post(
        "/api/v1/monitors",
        json={
            "url": "https://example.com",
            "interval_seconds": 60,
            "timeout_seconds": 10,
        },
    )

    assert response.status_code == 422


def test_create_monitor_rejects_missing_url(client):
    response = client.post(
        "/api/v1/monitors",
        json={
            "name": "Missing URL Monitor",
            "interval_seconds": 60,
            "timeout_seconds": 10,
        },
    )

    assert response.status_code == 422


def test_create_monitor_rejects_empty_name(client):
    response = client.post(
        "/api/v1/monitors",
        json={
            "name": "",
            "url": "https://example.com",
            "interval_seconds": 60,
            "timeout_seconds": 10,
        },
    )

    assert response.status_code == 422


def test_update_missing_monitor_returns_404(client):
    response = client.patch(
        "/api/v1/monitors/99999",
        json={"name": "Updated Name"},
    )

    assert response.status_code == 404


def test_update_monitor_rejects_invalid_url(client):
    created = create_monitor(client).json()

    response = client.patch(
        f"/api/v1/monitors/{created['id']}",
        json={"url": "not-a-valid-url"},
    )

    assert response.status_code == 422


def test_update_monitor_rejects_null_name(client):
    created = create_monitor(client).json()

    response = client.patch(
        f"/api/v1/monitors/{created['id']}",
        json={"name": None},
    )

    assert response.status_code == 422


def test_update_monitor_rejects_interval_below_minimum(client):
    created = create_monitor(client).json()

    response = client.patch(
        f"/api/v1/monitors/{created['id']}",
        json={"interval_seconds": 10},
    )

    assert response.status_code == 422
