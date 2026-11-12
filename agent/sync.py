
"""Sincronização segura da fila local de telemetria com a API central."""

import httpx

from agent.local_db import fetch_pending_readings, mark_readings_synced


def sync_pending(db_path, agent_id, api_url, batch_size=100, timeout=10):
    """
    Envia leituras pendentes à central.

    Os registros locais só são marcados como sincronizados após
    confirmação válida da API central.
    """
    pending = fetch_pending_readings(db_path, limit=batch_size)

    if not pending:
        return {
            "status": "empty",
            "sent": 0,
            "accepted": 0,
            "duplicated": 0,
            "synced": 0,
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

    url = f"{api_url.rstrip('/')}/api/sync/{agent_id}"

    try:
        response = httpx.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        result = response.json()

    except (httpx.HTTPError, ValueError) as exc:
        return {
            "status": "offline",
            "sent": len(pending),
            "accepted": 0,
            "duplicated": 0,
            "synced": 0,
            "error": str(exc),
        }

    accepted = result.get("accepted")
    duplicated = result.get("duplicated")
    total = result.get("total")

    if (
        result.get("status") != "ok"
        or not isinstance(accepted, int)
        or not isinstance(duplicated, int)
        or not isinstance(total, int)
        or accepted < 0
        or duplicated < 0
        or accepted + duplicated != len(pending)
        or total != len(pending)
    ):
        return {
            "status": "invalid_confirmation",
            "sent": len(pending),
            "accepted": 0,
            "duplicated": 0,
            "synced": 0,
        }

    event_ids = [row["event_id"] for row in pending]
    synced = mark_readings_synced(db_path, event_ids)

    return {
        "status": "ok",
        "sent": len(pending),
        "accepted": accepted,
        "duplicated": duplicated,
        "synced": synced,
    }
