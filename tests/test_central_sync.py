
from fastapi.testclient import TestClient

from central import auth

from central.main import create_app
from central.mtls import require_agent_certificate


def test_sync_accepts_batch_and_prevents_duplicates(tmp_path, monkeypatch):
    monkeypatch.setenv("VILA_AUTH_SECRET", "test-secret-" + "x" * 40)
    db_path = tmp_path / "central_sync.db"
    app = create_app(db_path=str(db_path))
    app.dependency_overrides[require_agent_certificate] = lambda: "centro"

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

        # Autentica a consulta humana após testar a sincronização do agente.
        secret = "JBSWY3DPEHPK3PXP"
        auth.create_operator(
            db_path, "sync_test", "Senha-Sync-Teste-123!", "admin", secret
        )
        user = auth.authenticate(
            db_path, "sync_test", "Senha-Sync-Teste-123!",
            auth._totp_counter(secret)
        )
        token = auth.issue_token(user)
        client.headers["Authorization"] = "Bearer " + token

        telemetry = client.get("/api/telemetry")

        assert telemetry.status_code == 200
        assert len(telemetry.json()) == 2


def test_sync_rejects_device_from_another_space(tmp_path):
    db_path = tmp_path / "central_invalid.db"
    app = create_app(db_path=str(db_path))
    app.dependency_overrides[require_agent_certificate] = lambda: "centro"

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
