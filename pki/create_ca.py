"""Cria a autoridade certificadora raiz da Rede Comunitária Vila Aurora."""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKI_DIR = ROOT / "data" / "pki" / "ca"
PRIVATE_DIR = PKI_DIR / "private"
CERTS_DIR = PKI_DIR / "certs"
CRL_DIR = PKI_DIR / "crl"
NEWCERTS_DIR = PKI_DIR / "newcerts"

CONFIG = ROOT / "pki" / "openssl.cnf"
KEY = PRIVATE_DIR / "ca.key"
CERT = PKI_DIR / "ca.crt"


def main():
    openssl = shutil.which("openssl")

    if not openssl:
        candidate = Path(r"C:\Program Files\OpenSSL-Win64\bin\openssl.exe")
        if candidate.exists():
            openssl = str(candidate)

    if not openssl:
        sys.exit("ERRO: executável OpenSSL não encontrado.")

    if not CONFIG.exists():
        sys.exit(f"ERRO: configuração não encontrada: {CONFIG}")

    if KEY.exists() or CERT.exists():
        sys.exit("ERRO: CA já existe. Não vou sobrescrever chaves ou certificados.")

    for directory in (PRIVATE_DIR, CERTS_DIR, CRL_DIR, NEWCERTS_DIR):
        directory.mkdir(parents=True, exist_ok=True)

    (PKI_DIR / "index.txt").touch()
    (PKI_DIR / "serial").write_text("1000\n", encoding="ascii")
    (PKI_DIR / "crlnumber").write_text("1000\n", encoding="ascii")

    print("Gerando chave privada da Root CA...")
    subprocess.run(
        [
            openssl, "genpkey",
            "-algorithm", "RSA",
            "-pkeyopt", "rsa_keygen_bits:3072",
            "-out", str(KEY),
        ],
        cwd=ROOT,
        check=True,
    )

    print("Gerando certificado raiz...")
    subprocess.run(
        [
            openssl, "req",
            "-new", "-x509",
            "-key", str(KEY),
            "-sha256",
            "-days", "3650",
            "-config", str(CONFIG),
            "-extensions", "v3_ca",
            "-out", str(CERT),
        ],
        cwd=ROOT,
        check=True,
    )

    print("\nRoot CA criada com sucesso.")
    print(f"Certificado público: {CERT.relative_to(ROOT)}")
    print(f"Chave privada:       {KEY.relative_to(ROOT)}")
    print("Validade:            3650 dias")


if __name__ == "__main__":
    main()
