"""Simulação básica de atuadores: bomba d'água com histerese."""


class WaterPump:
    """Liga quando o nível de água cai ao limite inferior e desliga no superior."""

    def __init__(self, low=30.0, high=80.0):
        if low >= high:
            raise ValueError("low deve ser menor que high")
        self.low = low
        self.high = high
        self.is_on = False

    def update(self, water_level_pct):
        if water_level_pct <= self.low:
            self.is_on = True
        elif water_level_pct >= self.high:
            self.is_on = False
        return self.is_on

    @property
    def state(self):
        return "on" if self.is_on else "off"
