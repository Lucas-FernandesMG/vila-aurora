import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPENSSL = r"C:\Program Files\OpenSSL-Win64\bin\openssl.exe"

CONFIG = ROOT / "pki" / "openssl.cnf"
CA_CERT = ROOT / "data" / "pki" / "ca" / "ca.crt"
CRL = ROOT / "data" / "pki" / "ca" / "crl" / "ca.crl"

test_id = datetime.now().strftime("%Y%m%d%H%M%S")
test_dir = ROOT / "data" / "pki" / f"revocation-test-{test_id}"
test_dir.mkdir(parents=True)

key = test_dir / "test.key"
csr = test_dir / "test.csr"
cert = test_dir / "test.crt"


def run(args, expected=True):
    result = subprocess.run(
        [OPENSSL, *map(str, args)],
        cwd=ROOT,
        capture_output=True,
        text=True
    )

    output = (result.stdout + result.stderr).strip()

    if expected and result.returncode != 0:
        print(output)
        raise RuntimeError("Comando OpenSSL falhou.")

    if not expected and result.returncode == 0:
        raise RuntimeError("O certificado revogado foi aceito. Teste falhou.")

    return output


def main():
    if not Path(OPENSSL).exists():
        raise FileNotFoundError("OpenSSL n?o encontrado.")

    if not CONFIG.exists() or not CA_CERT.exists():
        raise FileNotFoundError("Configura??o ou certificado da CA n?o encontrado.")

    print("[1/6] Emitindo certificado tempor?rio...")

    run([
        "req", "-new", "-newkey", "rsa:2048", "-nodes",
        "-keyout", key,
        "-out", csr,
        "-subj",
        f"/C=BR/O=Rede Comunitaria Vila Aurora/OU=Tests/CN=revocation-test-{test_id}"
    ])

    run([
        "ca", "-batch",
        "-config", CONFIG,
        "-extensions", "client_cert",
        "-in", csr,
        "-out", cert,
        "-notext"
    ])

    print("[2/6] Verificando certificado emitido...")

    print(run(["verify", "-CAfile", CA_CERT, cert]))

    print("[3/6] Revogando certificado de teste...")

    print(run([
        "ca", "-config", CONFIG,
        "-revoke", cert
    ]))

    print("[4/6] Atualizando CRL...")

    print(run([
        "ca", "-config", CONFIG,
        "-gencrl", "-out", CRL
    ]))

    print("[5/6] Validando assinatura da CRL...")

    print(run([
        "crl", "-in", CRL,
        "-CAfile", CA_CERT,
        "-verify", "-noout"
    ]))

    print("[6/6] Tentando validar certificado revogado...")

    output = run([
        "verify",
        "-crl_check",
        "-CAfile", CA_CERT,
        "-CRLfile", CRL,
        cert
    ], expected=False)

    print(output)

    if "certificate revoked" not in output.lower():
        raise RuntimeError("Falha: a rejei??o por revoga??o n?o foi confirmada.")

    print("\nRESULTADO: TESTE DE REVOGA??O APROVADO.")
    print(f"Certificado de teste: {cert.relative_to(ROOT)}")
    print(f"CRL atualizada: {CRL.relative_to(ROOT)}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"\nERRO: {error}")
        sys.exit(1)
