import pytest
from fastapi.testclient import TestClient

from central import auth, db
from central.main import create_app


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "central.db"


@pytest.fixture
def client(db_path, monkeypatch):
    monkeypatch.setenv("VILA_AUTH_SECRET", "test-secret-" + "x" * 40)
    with TestClient(create_app(db_path)) as c:
        secret = "JBSWY3DPEHPK3PXP"
        auth.create_operator(db_path, "test_admin", "Senha-Teste-123!", "admin", secret)
        token = c.post("/api/auth/login", json={
            "username": "test_admin",
            "password": "Senha-Teste-123!",
            "totp_code": auth._totp_counter(secret),
        }).json()["access_token"]
        c.headers["Authorization"] = "Bearer " + token
        yield c


def _insert_telemetry(db_path, n=3):
    with db.connect(db_path) as conn:
        for i in range(n):
            conn.execute(
                "INSERT INTO telemetry (space_id, device_id, metric, value, unit, recorded_at) "
                "VALUES ('centro', 'centro-agua-01', 'water_level_pct', ?, '%', ?)",
                (50.0 + i, f"2026-01-01T00:00:0{i}+00:00"))


def test_database_created_on_startup(db_path):
    assert not db_path.exists()
    with TestClient(create_app(db_path)):
        assert db_path.is_file()


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_list_spaces(client):
    r = client.get("/api/spaces")
    assert r.status_code == 200
    assert len(r.json()) == 5


def test_get_space(client):
    r = client.get("/api/spaces/ubs")
    assert r.status_code == 200
    assert r.json()["name"] == "UBS"


def test_unknown_space_returns_404(client):
    r = client.get("/api/spaces/inexistente")
    assert r.status_code == 404
    assert "detail" in r.json()


def test_devices_and_filter(client):
    assert len(client.get("/api/devices").json()) == 30
    assert len(client.get("/api/devices", params={"space_id": "horta"}).json()) == 6
    assert client.get("/api/devices", params={"space_id": "xxx"}).status_code == 404


def test_telemetry_empty_then_filtered(client, db_path):
    assert client.get("/api/telemetry").json() == []
    _insert_telemetry(db_path)
    rows = client.get("/api/telemetry").json()
    assert len(rows) == 3
    assert rows[0]["value"] == 52.0
    assert len(client.get("/api/telemetry", params={"space_id": "centro", "limit": 2}).json()) == 2
    assert client.get("/api/telemetry", params={"space_id": "escola"}).json() == []


def test_telemetry_validation_and_unknown_ids(client):
    assert client.get("/api/telemetry", params={"limit": 0}).status_code == 422
    assert client.get("/api/telemetry", params={"limit": 5000}).status_code == 422
    assert client.get("/api/telemetry", params={"offset": -1}).status_code == 422
    assert client.get("/api/telemetry", params={"space_id": "xxx"}).status_code == 404
    assert client.get("/api/telemetry", params={"device_id": "xxx"}).status_code == 404


def test_alerts(client, db_path):
    assert client.get("/api/alerts").json() == []
    with db.connect(db_path) as conn:
        conn.execute("INSERT INTO alerts (space_id, severity, message, created_at) "
                     "VALUES ('ubs', 'critical', 'teste', '2026-01-01T00:00:00+00:00')")
    alerts = client.get("/api/alerts", params={"severity": "critical"}).json()
    assert len(alerts) == 1 and alerts[0]["resolved"] is False
    assert client.get("/api/alerts", params={"severity": "grave"}).status_code == 422
    assert client.get("/api/alerts", params={"space_id": "xxx"}).status_code == 404


def test_status(client, db_path):
    _insert_telemetry(db_path, n=2)
    data = client.get("/api/status").json()
    assert data["status"] == "ok"
    assert data["spaces"] == 5 and data["devices"] == 30
    assert data["telemetry_readings"] == 2
    assert len(data["spaces_summary"]) == 5
