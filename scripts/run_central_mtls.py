"""Executa a API central com HTTPS e mTLS obrigatorio."""
import ssl
from pathlib import Path

import anyio
from anycorn import serve
from anycorn.config import Config

from central.main import app

ROOT = Path(__file__).resolve().parents[1]
PKI = ROOT / "data" / "pki"

CA_CERT = PKI / "ca" / "ca.crt"
CRL = PKI / "ca" / "crl" / "ca.crl"
SERVER_CERT = PKI / "mqtt" / "server.crt"
SERVER_KEY = PKI / "mqtt" / "server.key"
TRUST_BUNDLE = PKI / "ca" / "ca_with_crl.pem"


def prepare_trust_bundle():
    required = (CA_CERT, CRL, SERVER_CERT, SERVER_KEY)
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(f"Arquivo PKI ausente: {path}")

    TRUST_BUNDLE.write_bytes(
        CA_CERT.read_bytes().rstrip() + b"\n" + CRL.read_bytes().lstrip()
    )


async def main():
    prepare_trust_bundle()

    config = Config()
    config.bind = ["127.0.0.1:8443"]
    config.certfile = str(SERVER_CERT)
    config.keyfile = str(SERVER_KEY)
    config.ca_certs = str(TRUST_BUNDLE)
    config.verify_mode = ssl.CERT_REQUIRED
    config.verify_flags = ssl.VERIFY_CRL_CHECK_LEAF
    config.alpn_protocols = ["http/1.1"]
    config.accesslog = "-"
    config.errorlog = "-"

    print("API central HTTPS/mTLS: https://127.0.0.1:8443")
    print("Certificado de cliente obrigatorio; verificacao de CRL habilitada.")
    await serve(app, config)


if __name__ == "__main__":
    anyio.run(main)
