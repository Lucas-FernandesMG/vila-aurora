
"""Teste RT-23: continuidade offline e recuperação da sincronização."""

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from agent.config import load_all_configs
from agent.main import Agent
from agent.local_db import count_readings, fetch_pending_readings
from agent.sync import sync_pending


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def run_test(duration_minutes, interval_seconds, central_url):
    configs = load_all_configs()
    agents = {
        config.agent_id: Agent(config)
        for config in configs
    }

    started_at = now_utc()
    started = time.monotonic()

    offline_url = "http://127.0.0.1:1"

    print("=" * 60)
    print("RT-23 - TESTE DE CONTINUIDADE OFFLINE")
    print(f"Início: {started_at}")
    print(f"Duração prevista: {duration_minutes} minutos")
    print(f"Agentes: {len(agents)}")
    print("=" * 60)

    initial_counts = {
        agent_id: count_readings(agent.config.db_path)
        for agent_id, agent in agents.items()
    }

    cycles = 0

    while time.monotonic() - started < duration_minutes * 60:
        cycle_started = time.monotonic()

        for agent_id, agent in agents.items():
            agent.run_cycle()

            # Endpoint deliberadamente indisponível durante a simulação.
            result = sync_pending(
                agent.config.db_path,
                agent_id,
                offline_url,
                timeout=2,
            )

            if result["status"] != "offline":
                raise RuntimeError(
                    f"{agent_id}: endpoint de teste não ficou indisponível."
                )

        cycles += 1

        elapsed = time.monotonic() - started
        print(
            f"Ciclo {cycles} | "
            f"Tempo decorrido: {elapsed / 60:.2f} min"
        )

        remaining = interval_seconds - (
            time.monotonic() - cycle_started
        )

        if remaining > 0:
            time.sleep(min(remaining, max(0, duration_minutes * 60 - elapsed)))

    outage_ended_at = now_utc()
    actual_duration = (time.monotonic() - started) / 60

    print("\nIndisponibilidade encerrada.")
    print("Iniciando recuperação e sincronização...")

    synchronization = {}

    for agent_id, agent in agents.items():
        pending_before = len(
            fetch_pending_readings(agent.config.db_path, limit=100000)
        )

        result = sync_pending(
            agent.config.db_path,
            agent_id,
            central_url,
            batch_size=100000,
            timeout=30,
        )

        pending_after = len(
            fetch_pending_readings(agent.config.db_path, limit=100000)
        )

        synchronization[agent_id] = {
            "pending_before": pending_before,
            "pending_after": pending_after,
            "sync_result": result,
            "total_local": count_readings(agent.config.db_path),
        }

    finished_at = now_utc()

    report = {
        "test": "RT-23",
        "started_at": started_at,
        "outage_ended_at": outage_ended_at,
        "finished_at": finished_at,
        "planned_duration_minutes": duration_minutes,
        "actual_duration_minutes": round(actual_duration, 2),
        "cycles": cycles,
        "agents": len(agents),
        "synchronization": synchronization,
    }

    output_dir = Path("data/logs")
    output_dir.mkdir(parents=True, exist_ok=True)

    report_path = output_dir / "rt23_evidence.json"
    report_path.write_text(
        json.dumps(report, indent=4, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n" + "=" * 60)
    print("RESULTADO RT-23")
    print(json.dumps(report, indent=4, ensure_ascii=False))
    print(f"\nEvidência salva em: {report_path}")
    print("=" * 60)

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration-minutes", type=float, default=30)
    parser.add_argument("--interval-seconds", type=int, default=10)
    parser.add_argument(
        "--central-url",
        default="http://127.0.0.1:8000",
    )

    args = parser.parse_args()

    run_test(
        args.duration_minutes,
        args.interval_seconds,
        args.central_url,
    )
