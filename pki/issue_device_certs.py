"""Emite certificados mTLS individuais para os 30 dispositivos."""

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


def main():
    openssl = shutil.which("openssl")
    if not openssl:
        candidate = Path(r"C:\Program Files\OpenSSL-Win64\bin\openssl.exe")
        if candidate.exists():
            openssl = str(candidate)

    if not openssl:
        sys.exit("ERRO: OpenSSL não encontrado.")

    for path in (CA_CERT, CA_KEY, OPENSSL_CONFIG):
        if not path.exists():
            sys.exit(f"ERRO: arquivo ausente: {path}")

    devices = []
    seen = set()

    for config_file in sorted(CONFIG_DIR.glob("*.yaml")):
        data = json.loads(config_file.read_text(encoding="utf-8"))
        agent_id = data["agent_id"]

        for device in data.get("devices", []):
            device_id = device["id"]

            if not device_id.replace("-", "").isalnum():
                sys.exit(f"ID inválido: {device_id}")

            if device_id in seen:
                sys.exit(f"ID duplicado: {device_id}")

            seen.add(device_id)
            devices.append((agent_id, device_id))

    if len(devices) != 30:
        sys.exit(f"ERRO: esperados 30 dispositivos; encontrados {len(devices)}.")

    for agent_id, device_id in devices:
        folder = OUTPUT_DIR / agent_id / "devices" / device_id
        if any((folder / name).exists() for name in ("client.key", "client.crt", "client.csr")):
            sys.exit(f"ERRO: já existem arquivos para {device_id}. Nada foi emitido.")

    for agent_id, device_id in devices:
        folder = OUTPUT_DIR / agent_id / "devices" / device_id
        folder.mkdir(parents=True, exist_ok=True)

        key = folder / "client.key"
        csr = folder / "client.csr"
        cert = folder / "client.crt"

        print(f"Emitindo: {device_id}")

        subprocess.run([
            openssl, "genpkey", "-algorithm", "RSA",
            "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(key)
        ], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)

        subprocess.run([
            openssl, "req", "-new", "-key", str(key), "-sha256",
            "-subj", f"/C=BR/O=Rede Comunitaria Vila Aurora/OU={agent_id}/CN={device_id}",
            "-out", str(csr)
        ], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)

        subprocess.run([
            openssl, "ca", "-batch", "-notext",
            "-config", str(OPENSSL_CONFIG),
            "-extensions", "client_cert",
            "-days", "365",
            "-in", str(csr),
            "-out", str(cert)
        ], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)

        csr.unlink()

    print(f"\nSUCESSO: {len(devices)} certificados de dispositivos emitidos.")
    print(f"Local: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
