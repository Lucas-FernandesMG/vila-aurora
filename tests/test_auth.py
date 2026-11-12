import time

import pytest
from fastapi.testclient import TestClient

from central import auth
from central.main import create_app


@pytest.fixture
def auth_client(tmp_path, monkeypatch):
    monkeypatch.setenv("VILA_AUTH_SECRET", "test-secret-" + "x" * 40)
    path = tmp_path / "central.db"
    with TestClient(create_app(path)) as client:
        secret = "JBSWY3DPEHPK3PXP"
        auth.create_operator(path, "admin_test", "Senha-Forte-123!", "admin", secret)
        auth.create_operator(path, "auditor_test", "Senha-Forte-456!", "auditor", secret)
        yield client, secret


def totp(secret):
    return auth._totp_counter(secret)


def login(client, username, password, secret):
    return client.post("/api/auth/login", json={
        "username": username, "password": password, "totp_code": totp(secret)
    })


def test_login_requires_password_and_totp(auth_client):
    client, secret = auth_client
    assert login(client, "admin_test", "Senha-Forte-123!", secret).status_code == 200
    bad = client.post("/api/auth/login", json={
        "username": "admin_test", "password": "Senha-Forte-123!", "totp_code": "000000"
    })
    assert bad.status_code == 401


def test_protected_api_rejects_anonymous(auth_client):
    client, _ = auth_client
    assert client.get("/api/spaces").status_code == 401
    assert client.get("/health").status_code == 200


def test_authenticated_read_access(auth_client):
    client, secret = auth_client
    response = login(client, "auditor_test", "Senha-Forte-456!", secret)
    client.headers["Authorization"] = "Bearer " + response.json()["access_token"]
    assert client.get("/api/spaces").status_code == 200
    assert client.get("/api/auth/me").json()["role"] == "auditor"


def test_rbac_blocks_auditor_from_creating_operator(auth_client):
    client, secret = auth_client
    response = login(client, "auditor_test", "Senha-Forte-456!", secret)
    client.headers["Authorization"] = "Bearer " + response.json()["access_token"]
    result = client.post("/api/operators", json={
        "username": "new_operator", "password": "Senha-Nova-123!", "role": "operator"
    })
    assert result.status_code == 403


def test_admin_can_create_operator_and_receives_totp_setup(auth_client):
    client, secret = auth_client
    response = login(client, "admin_test", "Senha-Forte-123!", secret)
    client.headers["Authorization"] = "Bearer " + response.json()["access_token"]
    result = client.post("/api/operators", json={
        "username": "new_operator", "password": "Senha-Nova-123!", "role": "operator"
    })
    assert result.status_code == 201
    assert result.json()["totp_secret"]
    assert result.json()["provisioning_uri"].startswith("otpauth://totp/")


def test_expired_token_rejected(auth_client, monkeypatch):
    client, secret = auth_client
    response = login(client, "admin_test", "Senha-Forte-123!", secret)
    token = response.json()["access_token"]
    original_time = time.time
    monkeypatch.setattr(
        auth.time, "time",
        lambda: original_time() + auth.TOKEN_TTL_SECONDS + 1,
    )
    assert auth.resolve_token(client.app.state.db_path, token) is None
