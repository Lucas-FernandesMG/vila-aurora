"""Cria um operador local e apresenta o segredo TOTP para provisionamento."""
import getpass
import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from central import auth, db  # noqa: E402


def main():
    db_path = db.DEFAULT_DB_PATH
    db.init_db(db_path)
    auth.init_auth_db(db_path)
    username = input("Usuário: ").strip()
    password = getpass.getpass("Senha (mínimo 12 caracteres): ")
    confirm = getpass.getpass("Confirme a senha: ")
    if password != confirm:
        raise SystemExit("As senhas não conferem.")
    role = input("Papel [admin/operator/auditor] (padrão operator): ").strip() or "operator"
    secret = auth.create_operator(db_path, username, password, role)
    print("\nOperador criado.")
    print("Segredo TOTP (cadastre imediatamente no Aegis/Google Authenticator):")
    print(secret)
    print("\nURI de provisionamento:")
    print(auth.provisioning_uri(username, secret))
    print("\nGuarde o segredo em local seguro. Não o envie ao GitHub.")
    if role == "admin":
        print("ATENÇÃO: administrador criado. Restrinja o acesso ao computador e ao banco local.")


if __name__ == "__main__":
    main()
