import pytest

from agent.actuators_sim import WaterPump
from agent.config import AGENT_IDS, ConfigError, load_agent_config, load_all_configs
from agent.local_db import count_readings, fetch_readings
from agent.main import Agent

EXPECTED_METRICS = {"energy_w", "water_level_pct", "temperature_c", "humidity_pct",
                    "connectivity", "pump_on"}


@pytest.fixture
def configs(tmp_path):
    return load_all_configs(data_dir=tmp_path)


def test_five_yaml_configs_load(configs):
    assert [c.agent_id for c in configs] == list(AGENT_IDS)
    assert len({c.space_name for c in configs}) == 5
    for cfg in configs:
        assert cfg.devices
        assert len({d.id for d in cfg.devices}) == len(cfg.devices)


def test_missing_config_raises(tmp_path):
    with pytest.raises(ConfigError):
        load_agent_config("inexistente", data_dir=tmp_path)


def test_invalid_config_raises(tmp_path):
    (tmp_path / "x.yaml").write_text("agent_id: x\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_agent_config("x", config_dir=tmp_path, data_dir=tmp_path)


def test_local_databases_are_created(configs):
    agents = [Agent(c, seed=1) for c in configs]
    paths = [a.config.db_path for a in agents]
    assert all(p.is_file() for p in paths)
    assert len(set(paths)) == 5


def test_local_databases_are_independent(configs):
    agents = [Agent(c, seed=1) for c in configs]
    agents[0].run_cycle()
    agents[0].run_cycle()
    assert count_readings(agents[0].config.db_path) == 12
    for other in agents[1:]:
        assert count_readings(other.config.db_path) == 0
    agents[2].run_cycle()
    assert count_readings(agents[2].config.db_path) == 6
    assert count_readings(agents[0].config.db_path) == 12


def test_simulated_data_shape_and_ranges(configs):
    agent = Agent(configs[0], seed=42)
    for _ in range(50):
        readings = agent.run_cycle()
        assert {r["metric"] for r in readings} == EXPECTED_METRICS
        by_metric = {r["metric"]: r["value"] for r in readings}
        assert 0 <= by_metric["water_level_pct"] <= 100
        assert 15 <= by_metric["temperature_c"] <= 35
        assert 30 <= by_metric["humidity_pct"] <= 95
        assert by_metric["energy_w"] >= 0
        assert by_metric["connectivity"] in (0.0, 1.0)
        assert by_metric["pump_on"] in (0.0, 1.0)


def test_telemetry_is_registered_with_device_ids(configs):
    cfg = configs[1]
    agent = Agent(cfg, seed=7)
    agent.run_cycle()
    rows = fetch_readings(cfg.db_path)
    assert len(rows) == len(cfg.devices)
    assert {r["device_id"] for r in rows} == {d.id for d in cfg.devices}
    assert all(r["agent_id"] == cfg.agent_id for r in rows)


def test_pump_hysteresis():
    pump = WaterPump(low=30, high=80)
    assert pump.state == "off"
    assert pump.update(50) is False
    assert pump.update(25) is True
    assert pump.update(50) is True   # mantém ligada até o limite superior
    assert pump.update(85) is False
    assert pump.state == "off"


def test_pump_turns_on_during_long_run(configs):
    agent = Agent(configs[0], seed=3)
    states = [agent.run_cycle() and agent.pump.is_on for _ in range(80)]
    assert any(states)
