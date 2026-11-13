"""Correla??o defensiva de eventos sint?ticos e operacionais."""
from datetime import datetime, timezone, timedelta
import re


RULES = [
    {
        "id": "DET-SQLI-001",
        "patterns": (r"union\s+select", r"or\s+1\s*=\s*1", r"drop\s+table", r"sql\s+injection"),
        "severity": "critical",
        "title": "Poss?vel SQL injection",
        "action": "Bloquear a origem, preservar logs e revisar consultas.",
        "approval": True,
    },
    {
        "id": "DET-VPN-001",
        "patterns": (r"vpn.*02:1[0-9]", r"login.*02:1[0-9]", r"acesso.*madrugada"),
        "severity": "high",
        "title": "Acesso em hor?rio at?pico",
        "action": "Validar identidade, origem e MFA do acesso.",
        "approval": True,
    },
    {
        "id": "DET-WAN-001",
        "patterns": (r"wan.*down", r"internet.*indispon", r"conectividade.*perdida"),
        "severity": "high",
        "title": "Perda de conectividade externa",
        "action": "Manter opera??o local e armazenar dados para sincroniza??o.",
        "approval": False,
    },
    {
        "id": "DET-ACT-001",
        "patterns": (r"bomba.*agendamento.*alterado", r"pump.*schedule.*changed", r"atuador.*altera??o n?o autorizada"),
        "severity": "critical",
        "title": "Altera??o suspeita de atuador",
        "action": "Bloquear altera??o remota e exigir valida??o operacional.",
        "approval": True,
    },
    {
        "id": "DET-SENSOR-001",
        "patterns": (r"sensor.*sem.*leitura", r"cold.chain.*alert.*fail", r"temperatura.*sem.*alerta"),
        "severity": "high",
        "title": "Falha de monitoramento ambiental",
        "action": "Acionar verifica??o local e registrar condi??o degradada.",
        "approval": False,
    },
]


def correlate_events(events):
    """Gera alertas determin?sticos; n?o executa a??es sobre sistemas."""
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
                    "automated_action": "Nenhuma a??o destrutiva executada",
                })
                break
    return {
        "engine": "Vila Aurora Local Event Correlator",
        "events_analyzed": len(events),
        "detections": len(detections),
        "alerts": detections,
    }


def incident_timeline(events):
    """Ordena eventos por timestamp ISO-8601 quando dispon?vel."""
    return sorted(
        [e for e in events if isinstance(e, dict)],
        key=lambda e: str(e.get("timestamp", "")),
    )
