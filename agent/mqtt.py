"""Publicacao MQTT com identidade e certificado individual por dispositivo."""
import json
import re
import ssl
import threading
from pathlib import Path

import paho.mqtt.client as mqtt

ROOT = Path(__file__).resolve().parents[1]
PKI = ROOT / "data" / "pki"
AGENTS = PKI / "agents"
CA_CERT = PKI / "ca" / "ca.crt"


def build_mqtt_message(agent_id, reading):
    if not re.fullmatch(r"[a-z0-9_-]{1,64}", str(agent_id)):
        raise ValueError("agent_id invalido")

    device_id = str(reading.get("device_id", ""))
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,128}", device_id):
        raise ValueError("device_id invalido")

    topic = f"vila-aurora/{agent_id}/telemetry/{device_id}"
    payload = {
        "event_id": reading.get("event_id"),
        "agent_id": agent_id,
        "device_id": device_id,
        "metric": reading["metric"],
        "value": reading["value"],
        "unit": reading["unit"],
        "recorded_at": reading["recorded_at"],
    }
    return topic, json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


class MQTTPublisher:
    """Cliente MQTT autenticado pelo certificado individual do dispositivo."""

    def __init__(self, agent_id, device_id, host="127.0.0.1", port=8883, timeout=5):
        if not re.fullmatch(r"[a-z0-9_-]{1,64}", str(agent_id)):
            raise ValueError("agent_id invalido")
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,128}", str(device_id)):
            raise ValueError("device_id invalido")

        self.agent_id = agent_id
        self.device_id = device_id
        self.host = host
        self.port = int(port)
        self.timeout = float(timeout)
        self._connected = threading.Event()
        self._loop_started = False

        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"vila-aurora-{device_id}",
            protocol=mqtt.MQTTv311,
        )
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect

        device_dir = AGENTS / agent_id / "devices" / device_id
        cert_file = device_dir / "client.crt"
        key_file = device_dir / "client.key"

        for path in (CA_CERT, cert_file, key_file):
            if not path.is_file():
                raise FileNotFoundError(f"Arquivo PKI ausente: {path}")

        self._client.tls_set(
            ca_certs=str(CA_CERT),
            certfile=str(cert_file),
            keyfile=str(key_file),
            cert_reqs=ssl.CERT_REQUIRED,
            tls_version=ssl.PROTOCOL_TLS_CLIENT,
        )
        self._client.tls_insecure_set(False)

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if not getattr(reason_code, "is_failure", False):
            self._connected.set()
        else:
            self._connected.clear()

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        self._connected.clear()

    def connect(self):
        if self._connected.is_set():
            return True
        try:
            self._client.connect(self.host, self.port, keepalive=30)
            if not self._loop_started:
                self._client.loop_start()
                self._loop_started = True
            return self._connected.wait(self.timeout)
        except Exception:
            return False

    def publish_readings(self, readings):
        if not readings:
            return {"status": "empty", "published": 0}

        if any(str(item.get("device_id")) != self.device_id for item in readings):
            return {"status": "identity_mismatch", "published": 0}

        if not self.connect():
            return {"status": "offline", "published": 0}

        published = 0
        for reading in readings:
            try:
                topic, payload = build_mqtt_message(self.agent_id, reading)
                info = self._client.publish(topic, payload, qos=1, retain=False)
                if info.rc != mqtt.MQTT_ERR_SUCCESS:
                    return {"status": "publish_error", "published": published}
                info.wait_for_publish(timeout=self.timeout)
                if not info.is_published():
                    return {"status": "publish_timeout", "published": published}
                published += 1
            except Exception:
                return {"status": "publish_error", "published": published}

        return {"status": "ok", "published": published}

    def close(self):
        try:
            self._client.disconnect()
        finally:
            if self._loop_started:
                self._client.loop_stop()
                self._loop_started = False
            self._connected.clear()
