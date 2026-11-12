
"""Banco SQLite local de um agente, com fila de sincronização store-and-forward."""

import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS telemetry (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id    TEXT UNIQUE,
    agent_id    TEXT NOT NULL,
    device_id   TEXT NOT NULL,
    metric      TEXT NOT NULL,
    value       REAL NOT NULL,
    unit        TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    sync_status TEXT NOT NULL DEFAULT 'pending'
                CHECK (sync_status IN ('pending', 'synced'))
);

CREATE INDEX IF NOT EXISTS idx_local_telemetry_time
ON telemetry(recorded_at);

CREATE INDEX IF NOT EXISTS idx_local_telemetry_sync
ON telemetry(sync_status, id);
"""


@contextmanager
def connect(db_path):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _migrate_telemetry(conn):
    """Adiciona os campos de sincronização sem perder dados antigos."""

    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(telemetry)").fetchall()
    }

    if "event_id" not in columns:
        conn.execute("ALTER TABLE telemetry ADD COLUMN event_id TEXT")

    if "sync_status" not in columns:
        conn.execute(
            "ALTER TABLE telemetry ADD COLUMN sync_status TEXT "
            "NOT NULL DEFAULT 'pending'"
        )

    rows = conn.execute(
        "SELECT id FROM telemetry WHERE event_id IS NULL"
    ).fetchall()

    for row in rows:
        conn.execute(
            "UPDATE telemetry SET event_id = ? WHERE id = ?",
            (str(uuid.uuid4()), row["id"]),
        )

    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_local_telemetry_event "
        "ON telemetry(event_id)"
    )

    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_local_telemetry_sync "
        "ON telemetry(sync_status, id)"
    )


def init_local_db(db_path):
    """Cria ou atualiza o banco local do agente."""

    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with connect(path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS telemetry (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id    TEXT NOT NULL,
                device_id   TEXT NOT NULL,
                metric      TEXT NOT NULL,
                value       REAL NOT NULL,
                unit        TEXT NOT NULL,
                recorded_at TEXT NOT NULL
            )
        """)

        _migrate_telemetry(conn)

        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_local_telemetry_time "
            "ON telemetry(recorded_at)"
        )


def insert_readings(db_path, agent_id, readings):
    """Registra leituras localmente como pendentes de sincronização."""

    with connect(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO telemetry (
                event_id,
                agent_id,
                device_id,
                metric,
                value,
                unit,
                recorded_at,
                sync_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
            """,
            [
                (
                    str(uuid.uuid4()),
                    agent_id,
                    reading["device_id"],
                    reading["metric"],
                    reading["value"],
                    reading["unit"],
                    reading["recorded_at"],
                )
                for reading in readings
            ],
        )


def count_readings(db_path):
    """Retorna a quantidade total de leituras armazenadas."""

    with connect(db_path) as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM telemetry"
        ).fetchone()[0]


def fetch_readings(db_path, limit=100):
    """Consulta as leituras mais recentes."""

    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM telemetry ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()

    return [dict(row) for row in rows]


def fetch_pending_readings(db_path, limit=100):
    """Retorna eventos que ainda precisam ser enviados à central."""

    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM telemetry
            WHERE sync_status = 'pending'
            ORDER BY id ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [dict(row) for row in rows]


def mark_readings_synced(db_path, event_ids):
    """Marca como sincronizados somente os eventos confirmados pela central."""

    ids = list(dict.fromkeys(event_ids))

    if not ids:
        return 0

    with connect(db_path) as conn:
        placeholders = ",".join("?" for _ in ids)

        cursor = conn.execute(
            f"""
            UPDATE telemetry
            SET sync_status = 'synced'
            WHERE event_id IN ({placeholders})
              AND sync_status = 'pending'
            """,
            ids,
        )

        return cursor.rowcount
