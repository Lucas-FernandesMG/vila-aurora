import base64
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CENTRAL = ROOT / "data" / "vpn" / "central.conf"
CLIENT = ROOT / "data" / "vpn" / "segundo_ponto.conf"

def read_config(path):
    assert path.exists(), f"Arquivo ausente: {path}"
    result = {}
    section = None
    for raw in path.read_text(encoding="ascii").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            result[section] = {}
        elif "=" in line and section:
            key, value = line.split("=", 1)
            result[section][key.strip()] = value.strip()
    return result

def find_wg():
    candidates = [
        shutil.which("wg.exe"),
        shutil.which("wg"),
        r"C:\Program Files\WireGuard\wg.exe",
    ]
    return next((p for p in candidates if p and Path(p).exists()), None)

def derive_public(private_key):
    wg = find_wg()
    if not wg:
        return None
    result = subprocess.run(
        [wg, "pubkey"],
        input=private_key + "\n",
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()

def test_both_configurations_exist():
    assert CENTRAL.exists()
    assert CLIENT.exists()

def test_central_address_and_port():
    cfg = read_config(CENTRAL)
    interface = cfg["Interface"]
    assert interface["Address"] == "10.77.0.1/24"
    assert interface["ListenPort"] == "51820"
    assert cfg["Peer"]["AllowedIPs"] == "10.77.0.2/32"

def test_client_address_and_route():
    cfg = read_config(CLIENT)
    interface = cfg["Interface"]
    peer = cfg["Peer"]
    assert interface["Address"] == "10.77.0.2/32"
    assert peer["AllowedIPs"] == "10.77.0.0/24"
    assert peer["Endpoint"].endswith(":51820")
    assert interface["PrivateKey"] != peer["PublicKey"]

def test_keys_are_valid_wireguard_keys():
    for path in (CENTRAL, CLIENT):
        cfg = read_config(path)
        for section in cfg.values():
            for name in ("PrivateKey", "PublicKey"):
                if name in section:
                    decoded = base64.b64decode(section[name], validate=True)
                    assert len(decoded) == 32

def test_public_keys_match_private_keys():
    wg = find_wg()
    if not wg:
        import pytest
        pytest.skip("WireGuard wg.exe n?o encontrado; valida??o criptogr?fica adiada")

    central = read_config(CENTRAL)
    client = read_config(CLIENT)

    central_public = derive_public(central["Interface"]["PrivateKey"])
    client_public = derive_public(client["Interface"]["PrivateKey"])

    assert central_public == client["Peer"]["PublicKey"]
    assert client_public == central["Peer"]["PublicKey"]

def test_no_full_tunnel_or_unexpected_network():
    central = read_config(CENTRAL)
    client = read_config(CLIENT)
    assert "0.0.0.0/0" not in client["Peer"]["AllowedIPs"]
    assert central["Peer"]["AllowedIPs"] == "10.77.0.2/32"
