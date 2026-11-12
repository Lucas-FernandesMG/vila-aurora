
from fastapi.testclient import TestClient

from central.main import create_app


def test_sync_accepts_batch_and_prevents_duplicates(tmp_path):
    db_path = tmp_path / "central_sync.db"
    app = create_app(db_path=str(db_path))

    readings = [
        {
            "event_id": "event-sync-001",
            "device_id": "centro-energia-01",
            "metric": "energy",
            "value": 125.5,
            "unit": "kWh",
            "recorded_at": "2026-11-12T12:00:00"
        },
        {
            "event_id": "event-sync-002",
            "device_id": "centro-agua-01",
            "metric": "water_level",
            "value": 75.0,
            "unit": "%",
            "recorded_at": "2026-11-12T12:01:00"
        }
    ]

    with TestClient(app) as client:
        first = client.post(
            "/api/sync/centro",
            json={"readings": readings}
        )

        assert first.status_code == 200, first.text
        assert first.json()["accepted"] == 2
        assert first.json()["duplicated"] == 0

        second = client.post(
            "/api/sync/centro",
            json={"readings": readings}
        )

        assert second.status_code == 200
        assert second.json()["accepted"] == 0
        assert second.json()["duplicated"] == 2

        telemetry = client.get("/api/telemetry")

        assert telemetry.status_code == 200
        assert len(telemetry.json()) == 2


def test_sync_rejects_device_from_another_space(tmp_path):
    db_path = tmp_path / "central_invalid.db"
    app = create_app(db_path=str(db_path))

    readings = [
        {
            "event_id": "event-invalid-001",
            "device_id": "escola-energia",
            "metric": "energy",
            "value": 100,
            "unit": "kWh",
            "recorded_at": "2026-11-12T12:00:00"
        }
    ]

    with TestClient(app) as client:
        response = client.post(
            "/api/sync/centro",
            json={"readings": readings}
        )

        assert response.status_code == 400
