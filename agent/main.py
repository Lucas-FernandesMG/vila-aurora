"""Agente reutilizável: simula leituras e grava no banco SQLite local."""
import argparse
import random
import time

from agent.actuators_sim import WaterPump
from agent.config import AGENT_IDS, load_agent_config, load_all_configs
from agent.local_db import init_local_db, insert_readings
from agent.sensors_sim import SensorSimulator, utc_now_iso


class Agent:
    def __init__(self, config, seed=None):
        self.config = config
        self.pump = WaterPump()
        self.sensors = SensorSimulator(config, rng=random.Random(seed))
        init_local_db(config.db_path)

    def run_cycle(self):
        """Executa um ciclo: simula, atualiza a bomba e grava no banco local."""
        self.sensors.step(self.pump.is_on)
        self.pump.update(self.sensors.water_level)
        readings = self.sensors.read(self.pump.is_on, utc_now_iso())
        insert_readings(self.config.db_path, self.config.agent_id, readings)
        return readings


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Agente Vila Aurora")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--agent", choices=AGENT_IDS, help="identificador do agente")
    target.add_argument("--all", action="store_true", help="executa os cinco agentes em um processo")
    parser.add_argument("--cycles", type=int, default=0, help="número de ciclos (0 = até Ctrl+C)")
    parser.add_argument("--interval", type=float, default=5.0, help="segundos entre ciclos")
    parser.add_argument("--seed", type=int, default=None, help="semente aleatória (opcional)")
    args = parser.parse_args(argv)
    if args.cycles < 0:
        parser.error("--cycles deve ser >= 0")
    if args.interval < 0:
        parser.error("--interval deve ser >= 0")
    return args


def main(argv=None):
    args = parse_args(argv)
    configs = load_all_configs() if args.all else [load_agent_config(args.agent)]
    agents = [Agent(c, seed=args.seed) for c in configs]
    print("Agentes ativos: " + ", ".join(a.config.agent_id for a in agents))
    done = 0
    try:
        while args.cycles == 0 or done < args.cycles:
            for agent in agents:
                readings = agent.run_cycle()
                print(f"[{agent.config.agent_id}] {len(readings)} leituras gravadas "
                      f"(bomba: {agent.pump.state})")
            done += 1
            if args.cycles == 0 or done < args.cycles:
                time.sleep(args.interval)
    except KeyboardInterrupt:
        print("Agentes interrompidos.")


if __name__ == "__main__":
    main()
