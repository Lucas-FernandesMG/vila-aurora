
import pytest
from fastapi.testclient import TestClient

from agent.local_db import (
    init_local_db,
    insert_readings,
    fetch_pending_readings,
    count_readings,
    fetch_readings,
)
from agent.sync import sync_pending
from central.main import app


@pytest.fixture
def environment(tmp_path):
    db_path = tmp_path / "centro.db"
    init_local_db(db_path)

    readings = [
        {
            "device_id": "centro-energia-01",
            "metric": "energy_consumption",
            "value": 125.5,
            "unit": "kWh",
            "recorded_at": "2026-11-12T12:00:00Z",
        },
        {
            "device_id": "centro-agua-01",
            "metric": "water_level",
            "value": 45.0,
            "unit": "%",
            "recorded_at": "2026-11-12T12:00:10Z",
        },
    ]

    insert_readings(db_path, "centro", readings)

    return db_path


def test_offline_preserves_local_readings(environment):
    """A indisponibilidade da central não pode apagar leituras locais."""

    db_path = environment

    result = sync_pending(
        db_path,
        "centro",
        "http://127.0.0.1:1",
    )

    assert result["status"] == "offline"
    assert count_readings(db_path) == 2
    assert len(fetch_pending_readings(db_path)) == 2


def test_recovery_synchronizes_pending_readings(environment, tmp_path):
    """Após a recuperação, os eventos pendentes são enviados à central."""

    db_path = environment
    central_db = tmp_path / "central.db"

    from central import db

    db.init_db(central_db)

    app.state.db_path = str(central_db)

    with TestClient(app) as client:
        original_post = __import__("agent.sync", fromlist=["httpx"]).httpx.post

        def local_post(url, json, timeout):
            path = url.replace(
                "http://central.test",
                "",
            )
            return client.post(path, json=json)

        import agent.sync
        agent.sync.httpx.post = local_post

        try:
            result = sync_pending(
                db_path,
                "centro",
                "http://central.test",
            )
        finally:
            agent.sync.httpx.post = original_post

    assert result["status"] == "ok"
    assert result["accepted"] == 2
    assert result["synced"] == 2
    assert len(fetch_pending_readings(db_path)) == 0

    local_rows = fetch_readings(db_path)
    assert all(row["sync_status"] == "synced" for row in local_rows)


def test_repeated_sync_does_not_duplicate_events(environment, tmp_path):
    """Reenvio dos mesmos eventos não deve duplicar registros na central."""

    db_path = environment
    central_db = tmp_path / "central.db"

    from central import db

    db.init_db(central_db)
    app.state.db_path = str(central_db)

    with TestClient(app) as client:
        import agent.sync

        original_post = agent.sync.httpx.post

        def local_post(url, json, timeout):
            path = url.replace("http://central.test", "")
            return client.post(path, json=json)

        agent.sync.httpx.post = local_post

        try:
            first = sync_pending(db_path, "centro", "http://central.test")

            # Simula perda da confirmação: os eventos voltam a ficar pendentes.
            from agent.local_db import connect
            with connect(db_path) as conn:
                conn.execute(
                    "UPDATE telemetry SET sync_status = 'pending'"
                )

            second = sync_pending(db_path, "centro", "http://central.test")

        finally:
            agent.sync.httpx.post = original_post

    assert first["accepted"] == 2
    assert second["accepted"] == 0
    assert second["duplicated"] == 2

    central_rows = db.query_telemetry(db_path=str(central_db))
    assert len(central_rows) == 2
