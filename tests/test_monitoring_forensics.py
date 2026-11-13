import hashlib
import json

from central.monitoring import correlate_events, incident_timeline
from scripts.forensic_capture import capture_evidence, sha256_file


def test_detects_sql_injection_and_requires_approval():
    result = correlate_events([
        {"message": "SQL injection: UNION SELECT users", "source": "api"}
    ])
    assert result["detections"] == 1
    alert = result["alerts"][0]
    assert alert["rule_id"] == "DET-SQLI-001"
    assert alert["human_approval_required"] is True
    assert "Nenhuma ação destrutiva" in alert["automated_action"]


def test_wan_event_is_detected_without_high_impact_approval():
    result = correlate_events([
        {"message": "WAN down - conectividade perdida"}
    ])
    assert result["detections"] == 1
    assert result["alerts"][0]["rule_id"] == "DET-WAN-001"
    assert result["alerts"][0]["human_approval_required"] is False


def test_ignores_unrecognized_events():
    result = correlate_events([{"message": "Operação normal"}])
    assert result["detections"] == 0


def test_timeline_orders_events():
    events = [
        {"timestamp": "2026-11-13T12:02:00Z"},
        {"timestamp": "2026-11-13T12:01:00Z"},
    ]
    assert incident_timeline(events)[0]["timestamp"].endswith("12:01:00Z")


def test_forensic_capture_hash_and_manifest(tmp_path):
    source = tmp_path / "logs"
    source.mkdir()
    artifact = source / "application.log"
    artifact.write_text("evento de teste", encoding="utf-8")
    output = tmp_path / "evidence" / "manifest.json"

    manifest = capture_evidence(source, output)

    assert manifest["artifact_count"] == 1
    assert manifest["artifacts"][0]["sha256"] == hashlib.sha256(
        b"evento de teste"
    ).hexdigest()
    assert sha256_file(artifact) == manifest["artifacts"][0]["sha256"]
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["case_id"] == "INC-VA-0712"
