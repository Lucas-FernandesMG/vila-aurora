import sqlite3

import pytest

from central import db

EXPECTED_NAMES = [
    "Centro Comunitário", "Escola Municipal", "UBS",
    "Horta e Cozinha Solidária", "Abrigo de Emergência",
]


@pytest.fixture
def central_db(tmp_path):
    path = tmp_path / "nested" / "central.db"
    db.init_db(path)
    return path


def test_init_creates_database_and_tables(tmp_path):
    path = tmp_path / "nested" / "central.db"
    assert not path.exists()
    db.init_db(path)
    assert path.is_file()
    conn = sqlite3.connect(path)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    assert {"spaces", "devices", "telemetry", "alerts"} <= tables


def test_five_spaces_registered(central_db):
    spaces = db.list_spaces(central_db)
    assert [s["name"] for s in spaces] == EXPECTED_NAMES
    assert [s["id"] for s in spaces] == ["centro", "escola", "ubs", "horta", "abrigo"]


def test_devices_registered_for_every_space(central_db):
    for space in db.list_spaces(central_db):
        assert len(db.list_devices(central_db, space["id"])) == 6


def test_init_is_idempotent(central_db):
    db.init_db(central_db)
    assert len(db.list_spaces(central_db)) == 5
    assert len(db.list_devices(central_db)) == 30


def test_unknown_space_raises(central_db):
    with pytest.raises(db.NotFoundError):
        db.get_space(central_db, "inexistente")


def test_foreign_keys_enforced(central_db):
    with pytest.raises(sqlite3.IntegrityError):
        with db.connect(central_db) as conn:
            conn.execute(
                "INSERT INTO alerts (space_id, severity, message, created_at) "
                "VALUES ('nao-existe', 'info', 'x', '2026-01-01T00:00:00+00:00')")
