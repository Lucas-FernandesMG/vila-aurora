"""Simulação de sensores de um espaço comunitário."""
import random
from datetime import datetime, timezone

# tipo de dispositivo -> (métrica, unidade)
METRICS = {
    "energy": ("energy_w", "W"),
    "water_level": ("water_level_pct", "%"),
    "temperature": ("temperature_c", "C"),
    "humidity": ("humidity_pct", "%"),
    "connectivity": ("connectivity", "bool"),
    "pump": ("pump_on", "bool"),
}


def _clamp(value, low, high):
    return max(low, min(high, value))


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class SensorSimulator:
    """Gera leituras plausíveis para os dispositivos configurados."""

    def __init__(self, config, rng=None):
        self.config = config
        self.rng = rng or random.Random()
        self.water_level = self.rng.uniform(50, 70)
        self.temperature = self.rng.uniform(22, 28)
        self.humidity = self.rng.uniform(50, 70)
        self.base_energy_w = self.rng.uniform(300, 600)

    def step(self, pump_on):
        """Avança o estado físico simulado por um ciclo."""
        self.water_level = _clamp(
            self.water_level - self.rng.uniform(0.5, 2.5) + (4.0 if pump_on else 0.0), 0, 100)
        self.temperature = _clamp(self.temperature + self.rng.gauss(0, 0.4), 15, 35)
        self.humidity = _clamp(self.humidity + self.rng.gauss(0, 1.0), 30, 95)

    def read(self, pump_on, now=None):
        """Retorna uma leitura por dispositivo configurado (inclui o estado da bomba)."""
        now = now or utc_now_iso()
        energy = self.base_energy_w + self.rng.uniform(-50, 50) + (750 if pump_on else 0)
        online = 0 if self.rng.random() < 0.05 else 1
        values = {
            "energy": round(max(energy, 0), 1),
            "water_level": round(self.water_level, 1),
            "temperature": round(self.temperature, 1),
            "humidity": round(self.humidity, 1),
            "connectivity": online,
            "pump": 1 if pump_on else 0,
        }
        readings = []
        for device in self.config.devices:
            metric, unit = METRICS[device.type]
            readings.append({
                "device_id": device.id,
                "metric": metric,
                "value": float(values[device.type]),
                "unit": unit,
                "recorded_at": now,
            })
        return readings
