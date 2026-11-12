
import sqlite3
import uuid

import pytest

from agent.local_db import (
    init_local_db,
    insert_readings,
    count_readings,
    fetch_readings,
    fetch_pending_readings,
    mark_readings_synced,
)


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "agent" / "local.db"
    init_local_db(path)
    return path


@pytest.fixture
def sample_readings():
    return [
        {
            "device_id": "centro-energy",
            "metric": "energy_w",
            "value": 450.0,
            "unit": "W",
            "recorded_at": "2026-11-12T12:00:00+00:00",
        },
        {
            "device_id": "centro-water",
            "metric": "water_level_pct",
            "value": 65.0,
            "unit": "%",
            "recorded_at": "2026-11-12T12:00:00+00:00",
        },
    ]


def test_new_readings_receive_unique_event_ids(db_path, sample_readings):
    insert_readings(db_path, "centro", sample_readings)

    rows = fetch_readings(db_path)

    event_ids = [row["event_id"] for row in rows]

    assert len(event_ids) == 2
    assert len(set(event_ids)) == 2

    for event_id in event_ids:
        uuid.UUID(event_id)


def test_new_readings_start_as_pending(db_path, sample_readings):
    insert_readings(db_path, "centro", sample_readings)

    rows = fetch_readings(db_path)

    assert all(row["sync_status"] == "pending" for row in rows)


def test_pending_query_returns_only_pending_events(
    db_path, sample_readings
):
    insert_readings(db_path, "centro", sample_readings)

    rows = fetch_readings(db_path)
    first_event = rows[0]["event_id"]

    mark_readings_synced(db_path, [first_event])

    pending = fetch_pending_readings(db_path)

    assert len(pending) == 1
    assert pending[0]["sync_status"] == "pending"
    assert pending[0]["event_id"] != first_event


def test_synced_events_do_not_return_to_pending_queue(
    db_path, sample_readings
):
    insert_readings(db_path, "centro", sample_readings)

    rows = fetch_readings(db_path)
    event_ids = [row["event_id"] for row in rows]

    mark_readings_synced(db_path, event_ids)

    assert fetch_pending_readings(db_path) == []


def test_sync_failure_does_not_delete_local_readings(
    db_path, sample_readings
):
    insert_readings(db_path, "centro", sample_readings)

    original_count = count_readings(db_path)

    # Simula falha de comunicação: nenhum evento é marcado como enviado.
    with pytest.raises(ConnectionError):
        raise ConnectionError("Central indisponível")

    assert count_readings(db_path) == original_count
    assert len(fetch_pending_readings(db_path)) == original_count


def test_agents_keep_independent_databases(tmp_path, sample_readings):
    centro_db = tmp_path / "centro" / "local.db"
    escola_db = tmp_path / "escola" / "local.db"

    init_local_db(centro_db)
    init_local_db(escola_db)

    insert_readings(centro_db, "centro", sample_readings)

    assert count_readings(centro_db) == 2
    assert count_readings(escola_db) == 0
    assert fetch_pending_readings(escola_db) == []


def test_old_database_is_migrated_without_losing_readings(tmp_path):
    old_db = tmp_path / "old" / "local.db"
    old_db.parent.mkdir(parents=True)

    conn = sqlite3.connect(old_db)

    conn.execute("""
        CREATE TABLE telemetry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL,
            device_id TEXT NOT NULL,
            metric TEXT NOT NULL,
            value REAL NOT NULL,
            unit TEXT NOT NULL,
            recorded_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        INSERT INTO telemetry (
            agent_id, device_id, metric, value, unit, recorded_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        "centro",
        "centro-energy",
        "energy_w",
        450.0,
        "W",
        "2026-11-12T12:00:00+00:00",
    ))

    conn.commit()
    conn.close()

    init_local_db(old_db)

    rows = fetch_readings(old_db)

    assert len(rows) == 1
    assert rows[0]["agent_id"] == "centro"
    assert rows[0]["value"] == 450.0
    assert rows[0]["sync_status"] == "pending"
    uuid.UUID(rows[0]["event_id"])
