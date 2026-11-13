import json
import pytest

from agent.mqtt import build_mqtt_message


def test_mqtt_message_uses_space_scoped_topic_and_event_id():
    reading = {
        "event_id": "evt-123",
        "device_id": "centro-energia-01",
        "metric": "energy_w",
        "value": 125.5,
        "unit": "W",
        "recorded_at": "2026-11-13T12:00:00+00:00",
    }

    topic, payload = build_mqtt_message("centro", reading)
    data = json.loads(payload)

    assert topic == "vila-aurora/centro/telemetry/centro-energia-01"
    assert data["event_id"] == "evt-123"
    assert data["agent_id"] == "centro"
    assert data["device_id"] == "centro-energia-01"


@pytest.mark.parametrize("agent_id", ["../central", "Centro", "centro/#"])
def test_mqtt_message_rejects_invalid_agent_id(agent_id):
    with pytest.raises(ValueError):
        build_mqtt_message(agent_id, {"device_id": "device-1"})


def test_mqtt_message_rejects_invalid_device_id():
    with pytest.raises(ValueError):
        build_mqtt_message("centro", {"device_id": "../../escola"})
