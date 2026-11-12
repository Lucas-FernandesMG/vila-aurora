"""Sincronizacao HTTPS com certificado mTLS individual do agente."""
import ssl
from pathlib import Path

import httpx

from agent.local_db import fetch_pending_readings, mark_readings_synced

ROOT = Path(__file__).resolve().parents[1]
PKI = ROOT / "data" / "pki"
AGENTS = PKI / "agents"
CA_CERT = PKI / "ca" / "ca.crt"


def sync_pending(db_path, agent_id, api_url, batch_size=100, timeout=10, allow_insecure_http=False):
    pending = fetch_pending_readings(db_path, limit=batch_size)

    if not pending:
        return {
            "status": "empty", "sent": 0, "accepted": 0,
            "duplicated": 0, "synced": 0,
        }

    cert_file = AGENTS / agent_id / "client.crt"
    key_file = AGENTS / agent_id / "client.key"

    if not CA_CERT.is_file() or not cert_file.is_file() or not key_file.is_file():
        return {
            "status": "configuration_error", "sent": len(pending),
            "accepted": 0, "duplicated": 0, "synced": 0,
            "error": "CA, certificado ou chave privada ausente",
        }

    is_https = api_url.lower().startswith("https://")
    if not is_https and not (allow_insecure_http and api_url.lower().startswith("http://")):
        return {
            "status": "configuration_error", "sent": len(pending),
            "accepted": 0, "duplicated": 0, "synced": 0,
            "error": "A sincronizacao exige HTTPS",
        }

    payload = {
        "readings": [
            {
                "event_id": row["event_id"],
                "device_id": row["device_id"],
                "metric": row["metric"],
                "value": row["value"],
                "unit": row["unit"],
                "recorded_at": row["recorded_at"],
            }
            for row in pending
        ]
    }

    context = ssl.create_default_context(cafile=str(CA_CERT))
    context.load_cert_chain(certfile=str(cert_file), keyfile=str(key_file))

    url = f"{api_url.rstrip('/')}/api/sync/{agent_id}"

    try:
        request_options = {"json": payload, "timeout": timeout}
        if is_https:
            request_options["verify"] = context
        response = httpx.post(url, **request_options)
        response.raise_for_status()
        result = response.json()
    except (httpx.HTTPError, ValueError, OSError, ssl.SSLError) as exc:
        return {
            "status": "offline", "sent": len(pending),
            "accepted": 0, "duplicated": 0, "synced": 0,
            "error": str(exc),
        }

    accepted = result.get("accepted")
    duplicated = result.get("duplicated")
    total = result.get("total")

    if (
        result.get("status") != "ok"
        or result.get("agent_id") != agent_id
        or not isinstance(accepted, int)
        or not isinstance(duplicated, int)
        or not isinstance(total, int)
        or accepted < 0
        or duplicated < 0
        or accepted + duplicated != len(pending)
        or total != len(pending)
    ):
        return {
            "status": "invalid_confirmation", "sent": len(pending),
            "accepted": 0, "duplicated": 0, "synced": 0,
        }

    event_ids = [row["event_id"] for row in pending]
    synced = mark_readings_synced(db_path, event_ids)

    return {
        "status": "ok", "sent": len(pending),
        "accepted": accepted, "duplicated": duplicated, "synced": synced,
    }
