"""Emite certificados mTLS individuais para os cinco agentes."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config" / "agents"
OUTPUT_DIR = ROOT / "data" / "pki" / "agents"
CA_CERT = ROOT / "data" / "pki" / "ca" / "ca.crt"
CA_KEY = ROOT / "data" / "pki" / "ca" / "private" / "ca.key"
OPENSSL_CONFIG = ROOT / "pki" / "openssl.cnf"


def run_openssl(openssl, *args):
    subprocess.run(
        [openssl, *map(str, args)],
        cwd=ROOT,
        check=True,
    )


def main():
    openssl = shutil.which("openssl")

    if not openssl:
        candidate = Path(r"C:\Program Files\OpenSSL-Win64\bin\openssl.exe")
        if candidate.exists():
            openssl = str(candidate)

    if not openssl:
        sys.exit("ERRO: OpenSSL não encontrado.")

    for required in (CA_CERT, CA_KEY, OPENSSL_CONFIG):
        if not required.exists():
            sys.exit(f"ERRO: arquivo necessário não encontrado: {required}")

    configs = sorted(CONFIG_DIR.glob("*.yaml"))

    if not configs:
        sys.exit("ERRO: nenhum arquivo de agente encontrado.")

    agents = []

    for config_file in configs:
        data = json.loads(config_file.read_text(encoding="utf-8"))
        agent_id = data.get("agent_id")

        if not agent_id or not agent_id.replace("-", "").isalnum():
            sys.exit(f"ERRO: identificador inválido em {config_file.name}")

        agents.append(agent_id)

    if len(agents) != len(set(agents)):
        sys.exit("ERRO: identificadores de agentes duplicados.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for agent_id in agents:
        agent_dir = OUTPUT_DIR / agent_id
        key = agent_dir / "client.key"
        csr = agent_dir / "client.csr"
        cert = agent_dir / "client.crt"

        if key.exists() or csr.exists() or cert.exists():
            sys.exit(
                f"ERRO: já existem arquivos para {agent_id}. "
                "Nenhum certificado foi emitido nesta execução."
            )

    for agent_id in agents:
        agent_dir = OUTPUT_DIR / agent_id
        agent_dir.mkdir(parents=True, exist_ok=True)

        key = agent_dir / "client.key"
        csr = agent_dir / "client.csr"
        cert = agent_dir / "client.crt"

        print(f"\nEmitindo certificado: {agent_id}")

        run_openssl(
            openssl,
            "genpkey",
            "-algorithm", "RSA",
            "-pkeyopt", "rsa_keygen_bits:2048",
            "-out", key,
        )

        run_openssl(
            openssl,
            "req",
            "-new",
            "-key", key,
            "-sha256",
            "-subj", f"/C=BR/O=Rede Comunitaria Vila Aurora/OU=Edge Agents/CN={agent_id}",
            "-out", csr,
        )

        run_openssl(
            openssl,
            "ca",
            "-batch",
            "-notext",
            "-config", OPENSSL_CONFIG,
            "-extensions", "client_cert",
            "-days", "365",
            "-in", csr,
            "-out", cert,
        )

        csr.unlink()

        print(f"Certificado emitido: {cert.relative_to(ROOT)}")

    print(f"\nConcluído: {len(agents)} certificados emitidos.")
    print(f"Diretório: {OUTPUT_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
