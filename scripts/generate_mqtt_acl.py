"""Gera ACL Mosquitto a partir das configuracoes dos 30 dispositivos."""
from pathlib import Path
from agent.config import load_all_configs

root = Path(__file__).resolve().parents[1]
lines = [
    "# ACL gerada automaticamente; identidade MQTT = CN do certificado",
    "# Cada dispositivo publica somente no proprio topico.",
]

for config in load_all_configs():
    for device in config.devices:
        lines.extend([
            "",
            f"# {config.space_name} - {device.name}",
            f"user {device.id}",
            f"topic write vila-aurora/{config.agent_id}/telemetry/{device.id}",
            f"topic read vila-aurora/{config.agent_id}/commands/{device.id}/#",
        ])

lines.extend([
    "",
    "# CENTRAL",
    "user central",
    "topic read vila-aurora/+/telemetry/#",
    "topic read vila-aurora/+/status",
    "topic write vila-aurora/+/commands/#",
    "",
])

target = root / "config" / "mosquitto" / "acl.conf"
target.write_text("\n".join(lines), encoding="utf-8")
print(f"ACL gerada: {target}")
print(f"Identidades de dispositivos: {sum(len(c.devices) for c in load_all_configs())}")
