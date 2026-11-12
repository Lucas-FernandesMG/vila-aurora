"""Carregamento e validação das configurações dos agentes."""
from dataclasses import dataclass
from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_DIR = PROJECT_ROOT / "config" / "agents"
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"

AGENT_IDS = ("centro", "escola", "ubs", "horta", "abrigo")
DEVICE_TYPES = ("energy", "water_level", "temperature", "humidity", "connectivity", "pump")


class ConfigError(ValueError):
    """Configuração de agente ausente ou inválida."""


@dataclass(frozen=True)
class DeviceConfig:
    id: str
    name: str
    type: str


@dataclass(frozen=True)
class AgentConfig:
    agent_id: str
    space_name: str
    space_kind: str
    db_path: Path
    devices: tuple


def load_agent_config(agent_id, config_dir=None, data_dir=None):
    if agent_id not in AGENT_IDS:
        raise ConfigError(f"Agente desconhecido: {agent_id}")

    config_dir = Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
    data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
    path = config_dir / f"{agent_id}.yaml"

    if not path.is_file():
        raise ConfigError(f"Configuração não encontrada: {path}")

    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ConfigError(f"Configuração inválida em {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError(f"{path} deve conter um objeto JSON")

    for key in ("agent_id", "space_name", "space_kind", "local_db", "devices"):
        if not raw.get(key):
            raise ConfigError(f"{path}: campo obrigatório ausente: {key}")

    if raw["agent_id"] != agent_id:
        raise ConfigError(f"{path}: agent_id incorreto")

    local_db = Path(str(raw["local_db"]))

    if local_db.is_absolute() or ".." in local_db.parts:
        raise ConfigError(f"{path}: local_db deve ser relativo à pasta de dados")

    if not isinstance(raw["devices"], list):
        raise ConfigError(f"{path}: devices deve ser uma lista")

    devices = []
    seen = set()

    for item in raw["devices"]:
        if not isinstance(item, dict) or not all(item.get(k) for k in ("id", "name", "type")):
            raise ConfigError(f"{path}: dispositivo inválido: {item!r}")

        if item["type"] not in DEVICE_TYPES:
            raise ConfigError(f"{path}: tipo de dispositivo desconhecido: {item['type']}")

        if item["id"] in seen:
            raise ConfigError(f"{path}: id de dispositivo duplicado: {item['id']}")

        seen.add(item["id"])
        devices.append(DeviceConfig(item["id"], item["name"], item["type"]))

    return AgentConfig(
        agent_id=raw["agent_id"],
        space_name=raw["space_name"],
        space_kind=raw["space_kind"],
        db_path=data_dir / local_db,
        devices=tuple(devices),
    )


def load_all_configs(config_dir=None, data_dir=None):
    return [load_agent_config(a, config_dir, data_dir) for a in AGENT_IDS]
