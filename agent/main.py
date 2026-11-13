"""Agente reutilizavel: simula, armazena e transmite telemetria."""
import argparse
import random
import time

from agent.actuators_sim import WaterPump
from agent.config import AGENT_IDS, load_agent_config, load_all_configs
from agent.local_db import fetch_readings, init_local_db, insert_readings
from agent.sensors_sim import SensorSimulator, utc_now_iso
from agent.mqtt import MQTTPublisher
from agent.sync import sync_pending


class Agent:
    def __init__(self, config, seed=None, mqtt_publishers=None):
        self.config = config
        self.pump = WaterPump()
        self.sensors = SensorSimulator(config, rng=random.Random(seed))
        self.mqtt_publishers = mqtt_publishers or {}
        init_local_db(config.db_path)

    def run_cycle(self):
        """Persiste as leituras antes de tentar qualquer comunicacao."""
        self.sensors.step(self.pump.is_on)
        self.pump.update(self.sensors.water_level)
        readings = self.sensors.read(self.pump.is_on, utc_now_iso())

        insert_readings(self.config.db_path, self.config.agent_id, readings)

        if self.mqtt_publishers:
            stored = list(reversed(
                fetch_readings(self.config.db_path, limit=len(readings))
            ))
            for reading in stored:
                device_id = reading.get("device_id")
                publisher = self.mqtt_publishers.get(device_id)
                if publisher is None:
                    print(f"[{self.config.agent_id}/{device_id}] certificado MQTT indisponivel")
                    continue
                result = publisher.publish_readings([reading])
                if result["status"] != "ok":
                    print(
                        f"[{self.config.agent_id}/{device_id}] MQTT {result['status']}; "
                        "leitura mantida localmente"
                    )

        return readings


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Agente Vila Aurora")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--agent", choices=AGENT_IDS)
    target.add_argument("--all", action="store_true")

    parser.add_argument("--cycles", type=int, default=0)
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--mqtt", action="store_true")
    parser.add_argument("--mqtt-host", default="127.0.0.1")
    parser.add_argument("--mqtt-port", type=int, default=8883)
    parser.add_argument("--sync-url", default=None)
    parser.add_argument("--sync-every", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=100)

    args = parser.parse_args(argv)
    if args.cycles < 0 or args.interval < 0:
        parser.error("cycles e interval devem ser >= 0")
    if not 1 <= args.mqtt_port <= 65535:
        parser.error("mqtt-port deve estar entre 1 e 65535")
    if args.sync_every < 1 or args.batch_size < 1:
        parser.error("sync-every e batch-size devem ser >= 1")
    if args.sync_url and not args.sync_url.lower().startswith("https://"):
        parser.error("sync-url deve usar HTTPS")
    return args


def main(argv=None):
    args = parse_args(argv)
    configs = load_all_configs() if args.all else [load_agent_config(args.agent)]
    agents = []
    publishers = []

    for config in configs:
        device_publishers = {}
        if args.mqtt:
            for device in config.devices:
                try:
                    publisher = MQTTPublisher(
                        config.agent_id,
                        device.id,
                        args.mqtt_host,
                        args.mqtt_port,
                    )
                    device_publishers[device.id] = publisher
                    publishers.append(publisher)
                except (OSError, ValueError) as exc:
                    print(f"[{config.agent_id}/{device.id}] MQTT indisponivel: {exc}")

        agents.append(
            Agent(config, seed=args.seed, mqtt_publishers=device_publishers)
        )

    print("Agentes ativos: " + ", ".join(a.config.agent_id for a in agents))
    if args.mqtt:
        print(f"MQTT mTLS individual: {args.mqtt_host}:{args.mqtt_port}")
    if args.sync_url:
        print(f"HTTPS mTLS: {args.sync_url}")

    done = 0
    try:
        while args.cycles == 0 or done < args.cycles:
            for agent in agents:
                readings = agent.run_cycle()
                print(
                    f"[{agent.config.agent_id}] {len(readings)} leituras "
                    f"gravadas localmente (bomba: {agent.pump.state})"
                )
                if args.sync_url and (done + 1) % args.sync_every == 0:
                    result = sync_pending(
                        agent.config.db_path,
                        agent.config.agent_id,
                        args.sync_url,
                        batch_size=args.batch_size,
                    )
                    print(
                        f"[{agent.config.agent_id}] HTTPS sync: "
                        f"{result['status']} ({result.get('synced', 0)} sincronizadas)"
                    )
            done += 1
            if args.cycles == 0 or done < args.cycles:
                time.sleep(args.interval)
    except KeyboardInterrupt:
        print("Agentes interrompidos.")
    finally:
        for publisher in publishers:
            publisher.close()


if __name__ == "__main__":
    main()
