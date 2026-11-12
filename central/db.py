
"""Banco SQLite central: criação automática, carga inicial e consultas."""

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from agent.config import DEFAULT_CONFIG_DIR, DEFAULT_DATA_DIR, load_all_configs


DEFAULT_DB_PATH = Path(
    os.environ.get(
        "VILA_CENTRAL_DB",
        DEFAULT_DATA_DIR / "central" / "central.db",
    )
)


SCHEMA = """
CREATE TABLE IF NOT EXISTS spaces (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL UNIQUE,
    kind       TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS devices (
    id         TEXT PRIMARY KEY,
    space_id   TEXT NOT NULL REFERENCES spaces(id),
    name       TEXT NOT NULL,
    type       TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS telemetry (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id    TEXT UNIQUE,
    space_id    TEXT NOT NULL REFERENCES spaces(id),
    device_id   TEXT NOT NULL REFERENCES devices(id),
    metric      TEXT NOT NULL,
    value       REAL NOT NULL,
    unit        TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_telemetry_space_time
ON telemetry(space_id, recorded_at);

CREATE TABLE IF NOT EXISTS alerts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    space_id   TEXT NOT NULL REFERENCES spaces(id),
    device_id  TEXT REFERENCES devices(id),
    severity   TEXT NOT NULL CHECK (
        severity IN ('info', 'warning', 'critical')
    ),
    message    TEXT NOT NULL,
    resolved   INTEGER NOT NULL DEFAULT 0 CHECK (resolved IN (0, 1)),
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_alerts_space
ON alerts(space_id, created_at);
"""


class NotFoundError(LookupError):
    """Recurso inexistente."""


@contextmanager
def connect(db_path):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _migrate_telemetry(conn):
    """Adiciona event_id sem perder registros da central antiga."""

    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(telemetry)").fetchall()
    }

    if "event_id" not in columns:
        conn.execute("ALTER TABLE telemetry ADD COLUMN event_id TEXT")

    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_telemetry_event "
        "ON telemetry(event_id)"
    )


def init_db(db_path=None, config_dir=None):
    """Cria o banco e cadastra espaços e dispositivos."""

    db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)

    configs = load_all_configs(config_dir or DEFAULT_CONFIG_DIR)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    with connect(db_path) as conn:
        conn.executescript(SCHEMA)
        _migrate_telemetry(conn)

        for cfg in configs:
            conn.execute(
                """
                INSERT OR IGNORE INTO spaces
                (id, name, kind, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (cfg.agent_id, cfg.space_name, cfg.space_kind, now),
            )

            for dev in cfg.devices:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO devices
                    (id, space_id, name, type, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (dev.id, cfg.agent_id, dev.name, dev.type, now),
                )

    return db_path


def _rows(conn, sql, params=()):
    return [
        dict(row)
        for row in conn.execute(sql, params).fetchall()
    ]


def _require(conn, table, item_id, label):
    if conn.execute(
        f"SELECT 1 FROM {table} WHERE id = ?",
        (item_id,),
    ).fetchone() is None:
        raise NotFoundError(f"{label} não encontrado: {item_id}")


def receive_telemetry_batch(db_path, agent_id, readings):
    """
    Recebe um lote de eventos de um agente.

    Eventos repetidos são ignorados pelo event_id.
    Retorna a quantidade de eventos novos e duplicados.
    """

    if not isinstance(readings, list):
        raise ValueError("readings deve ser uma lista")

    accepted = 0
    duplicated = 0

    with connect(db_path) as conn:
        _require(conn, "spaces", agent_id, "Agente")

        for reading in readings:
            required = {
                "event_id",
                "device_id",
                "metric",
                "value",
                "unit",
                "recorded_at",
            }

            if not isinstance(reading, dict):
                raise ValueError("Evento deve ser um objeto")

            missing = required - reading.keys()

            if missing:
                raise ValueError(
                    f"Campos ausentes no evento: {', '.join(sorted(missing))}"
                )

            device = conn.execute(
                "SELECT space_id FROM devices WHERE id = ?",
                (reading["device_id"],),
            ).fetchone()

            if device is None:
                raise ValueError(
                    f"Dispositivo desconhecido: {reading['device_id']}"
                )

            if device["space_id"] != agent_id:
                raise ValueError(
                    "Dispositivo não pertence ao agente informado"
                )

            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO telemetry (
                    event_id,
                    space_id,
                    device_id,
                    metric,
                    value,
                    unit,
                    recorded_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    reading["event_id"],
                    agent_id,
                    reading["device_id"],
                    reading["metric"],
                    float(reading["value"]),
                    reading["unit"],
                    reading["recorded_at"],
                ),
            )

            if cursor.rowcount == 1:
                accepted += 1
            else:
                duplicated += 1

    return {
        "accepted": accepted,
        "duplicated": duplicated,
        "total": accepted + duplicated,
    }


def get_space(db_path, space_id):
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM spaces WHERE id = ?",
            (space_id,),
        ).fetchone()

    if row is None:
        raise NotFoundError(f"Espaço não encontrado: {space_id}")

    return dict(row)


def list_spaces(db_path):
    with connect(db_path) as conn:
        return _rows(
            conn,
            "SELECT * FROM spaces ORDER BY rowid",
        )


def list_devices(db_path, space_id=None):
    with connect(db_path) as conn:
        if space_id is not None:
            _require(conn, "spaces", space_id, "Espaço")

            return _rows(
                conn,
                "SELECT * FROM devices WHERE space_id = ? ORDER BY rowid",
                (space_id,),
            )

        return _rows(
            conn,
            "SELECT * FROM devices ORDER BY rowid",
        )


def query_telemetry(
    db_path,
    space_id=None,
    device_id=None,
    metric=None,
    limit=100,
    offset=0,
):
    with connect(db_path) as conn:
        if space_id is not None:
            _require(conn, "spaces", space_id, "Espaço")

        if device_id is not None:
            _require(conn, "devices", device_id, "Dispositivo")

        where = []
        params = []

        for column, value in (
            ("space_id", space_id),
            ("device_id", device_id),
            ("metric", metric),
        ):
            if value is not None:
                where.append(f"{column} = ?")
                params.append(value)

        sql = "SELECT * FROM telemetry"

        if where:
            sql += " WHERE " + " AND ".join(where)

        sql += " ORDER BY recorded_at DESC, id DESC LIMIT ? OFFSET ?"

        return _rows(
            conn,
            sql,
            (*params, limit, offset),
        )


def list_alerts(
    db_path,
    space_id=None,
    severity=None,
    resolved=None,
    limit=100,
    offset=0,
):
    with connect(db_path) as conn:
        if space_id is not None:
            _require(conn, "spaces", space_id, "Espaço")

        where = []
        params = []

        if space_id is not None:
            where.append("space_id = ?")
            params.append(space_id)

        if severity is not None:
            where.append("severity = ?")
            params.append(severity)

        if resolved is not None:
            where.append("resolved = ?")
            params.append(1 if resolved else 0)

        sql = "SELECT * FROM alerts"

        if where:
            sql += " WHERE " + " AND ".join(where)

        sql += " ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?"

        alerts = _rows(
            conn,
            sql,
            (*params, limit, offset),
        )

    for alert in alerts:
        alert["resolved"] = bool(alert["resolved"])

    return alerts


def get_status(db_path):
    with connect(db_path) as conn:
        spaces = _rows(
            conn,
            """
            SELECT s.id, s.name,
                   (SELECT COUNT(*) FROM devices d
                    WHERE d.space_id = s.id) AS devices,
                   (SELECT COUNT(*) FROM telemetry t
                    WHERE t.space_id = s.id) AS telemetry_readings,
                   (SELECT MAX(recorded_at) FROM telemetry t
                    WHERE t.space_id = s.id) AS last_reading_at,
                   (SELECT COUNT(*) FROM alerts a
                    WHERE a.space_id = s.id AND a.resolved = 0) AS open_alerts
            FROM spaces s
            ORDER BY s.rowid
            """,
        )

        totals = {
            "spaces": conn.execute(
                "SELECT COUNT(*) FROM spaces"
            ).fetchone()[0],
            "devices": conn.execute(
                "SELECT COUNT(*) FROM devices"
            ).fetchone()[0],
            "telemetry_readings": conn.execute(
                "SELECT COUNT(*) FROM telemetry"
            ).fetchone()[0],
            "open_alerts": conn.execute(
                "SELECT COUNT(*) FROM alerts WHERE resolved = 0"
            ).fetchone()[0],
        }

    return {
        "status": "ok",
        "database": "ok",
        **totals,
        "spaces_summary": spaces,
    }


def check_db(db_path):
    with connect(db_path) as conn:
        conn.execute("SELECT 1").fetchone()
