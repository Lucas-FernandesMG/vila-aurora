"""Captura de evid?ncias com hash SHA-256 e registro de cust?dia."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def capture_evidence(source_dir, output_file, case_id="INC-VA-0712", custodian="Equipe Vila Aurora"):
    source_dir = Path(source_dir)
    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    artifacts = []
    if source_dir.exists():
        for path in sorted(source_dir.rglob("*")):
            if path.is_file() and path.resolve() != output_file.resolve():
                stat = path.stat()
                artifacts.append({
                    "file": str(path),
                    "size_bytes": stat.st_size,
                    "modified_utc": datetime.fromtimestamp(
                        stat.st_mtime, timezone.utc
                    ).isoformat(),
                    "sha256": sha256_file(path),
                })

    manifest = {
        "case_id": case_id,
        "capture_time_utc": datetime.now(timezone.utc).isoformat(),
        "custodian": custodian,
        "method": "SHA-256",
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
        "limitations": [
            "Manifesto registra o estado dos arquivos no momento da captura.",
            "N?o comprova, isoladamente, a autenticidade anterior dos logs.",
            "Cust?dia f?sica e transfer?ncias devem ser registradas pelos respons?veis.",
        ],
    }
    output_file.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="data/logs")
    parser.add_argument("--output", default="data/forensics/INC-VA-0712_manifest.json")
    parser.add_argument("--case", default="INC-VA-0712")
    args = parser.parse_args()
    result = capture_evidence(args.source, args.output, args.case)
    print(f"Captura conclu?da: {result['artifact_count']} arquivo(s).")
    print(f"Manifesto: {args.output}")


if __name__ == "__main__":
    main()
