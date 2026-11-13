"""Correlação defensiva de eventos sintéticos e operacionais."""
from datetime import datetime, timezone, timedelta
import re


RULES = [
    {
        "id": "DET-SQLI-001",
        "patterns": (r"union\s+select", r"or\s+1\s*=\s*1", r"drop\s+table", r"sql\s+injection"),
        "severity": "critical",
        "title": "Possível SQL injection",
        "action": "Bloquear a origem, preservar logs e revisar consultas.",
        "approval": True,
    },
    {
        "id": "DET-VPN-001",
        "patterns": (r"vpn.*02:1[0-9]", r"login.*02:1[0-9]", r"acesso.*madrugada"),
        "severity": "high",
        "title": "Acesso em horário atípico",
        "action": "Validar identidade, origem e MFA do acesso.",
        "approval": True,
    },
    {
        "id": "DET-WAN-001",
        "patterns": (r"wan.*down", r"internet.*indispon", r"conectividade.*perdida"),
        "severity": "high",
        "title": "Perda de conectividade externa",
        "action": "Manter operação local e armazenar dados para sincronização.",
        "approval": False,
    },
    {
        "id": "DET-ACT-001",
        "patterns": (r"bomba.*agendamento.*alterado", r"pump.*schedule.*changed", r"atuador.*alteração não autorizada"),
        "severity": "critical",
        "title": "Alteração suspeita de atuador",
        "action": "Bloquear alteração remota e exigir validação operacional.",
        "approval": True,
    },
    {
        "id": "DET-SENSOR-001",
        "patterns": (r"sensor.*sem.*leitura", r"cold.chain.*alert.*fail", r"temperatura.*sem.*alerta"),
        "severity": "high",
        "title": "Falha de monitoramento ambiental",
        "action": "Acionar verificação local e registrar condição degradada.",
        "approval": False,
    },
]


def correlate_events(events):
    """Gera alertas determinísticos; não executa ações sobre sistemas."""
    detections = []
    for event in events:
        if not isinstance(event, dict):
            continue
        message = str(event.get("message", ""))
        normalized = message.lower()
        for rule in RULES:
            if any(re.search(pattern, normalized, re.IGNORECASE)
                   for pattern in rule["patterns"]):
                detections.append({
                    "rule_id": rule["id"],
                    "severity": rule["severity"],
                    "title": rule["title"],
                    "message": message[:500],
                    "timestamp": event.get("timestamp"),
                    "source": str(event.get("source", "unknown"))[:100],
                    "recommended_action": rule["action"],
                    "human_approval_required": rule["approval"],
                    "automated_action": "Nenhuma ação destrutiva executada",
                })
                break
    return {
        "engine": "Vila Aurora Local Event Correlator",
        "events_analyzed": len(events),
        "detections": len(detections),
        "alerts": detections,
    }


def incident_timeline(events):
    """Ordena eventos por timestamp ISO-8601 quando disponível."""
    return sorted(
        [e for e in events if isinstance(e, dict)],
        key=lambda e: str(e.get("timestamp", "")),
    )
