"""Autenticação local: PBKDF2, TOTP RFC 6238 e tokens HMAC."""
import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import struct
import time
from pathlib import Path
from urllib.parse import quote

ROLES = {"admin", "operator", "auditor"}
TOKEN_TTL_SECONDS = 8 * 60 * 60
_ITERATIONS = 310_000


def _connect(db_path):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_auth_db(db_path):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with _connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS operators (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                totp_secret TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin','operator','auditor')),
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)


def _password_hash(password, salt):
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _ITERATIONS
    ).hex()


def create_operator(db_path, username, password, role="operator", totp_secret=None):
    username = username.strip()
    if not 3 <= len(username) <= 64:
        raise ValueError("Usuário deve ter entre 3 e 64 caracteres")
    if len(password) < 12:
        raise ValueError("A senha deve ter pelo menos 12 caracteres")
    if role not in ROLES:
        raise ValueError("Papel inválido")
    secret = totp_secret or base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")
    salt = secrets.token_bytes(16)
    with _connect(db_path) as conn:
        conn.execute(
            """INSERT INTO operators
               (username,password_hash,password_salt,totp_secret,role)
               VALUES (?,?,?,?,?)""",
            (username, _password_hash(password, salt), salt.hex(), secret, role),
        )
    return secret


def _totp_counter(secret, timestamp=None):
    timestamp = time.time() if timestamp is None else timestamp
    key = base64.b32decode(secret + "=" * ((8 - len(secret) % 8) % 8))
    counter = int(timestamp // 30)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    number = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7fffffff
    return f"{number % 1_000_000:06d}"


def verify_totp(secret, code, timestamp=None):
    if not isinstance(code, str) or len(code) != 6 or not code.isdigit():
        return False
    now = time.time() if timestamp is None else timestamp
    # Janela de tolerância de 30 segundos para pequenas diferenças de relógio.
    return any(
        hmac.compare_digest(_totp_counter(secret, now + drift * 30), code)
        for drift in (-1, 0, 1)
    )


def provisioning_uri(username, secret, issuer="Vila Aurora"):
    label = quote(f"{issuer}:{username}")
    return (
        f"otpauth://totp/{label}?secret={secret}&issuer={quote(issuer)}"
        "&algorithm=SHA1&digits=6&period=30"
    )


def authenticate(db_path, username, password, totp_code):
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM operators WHERE username = ? AND active = 1",
            (username,),
        ).fetchone()
    if row is None:
        # Hash fictício para reduzir diferença grosseira de tempo para usuário inexistente.
        _password_hash(password or "", b"\0" * 16)
        return None
    try:
        salt = bytes.fromhex(row["password_salt"])
        expected = row["password_hash"]
        actual = _password_hash(password or "", salt)
        password_ok = hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        password_ok = False
    if not password_ok or not verify_totp(row["totp_secret"], totp_code):
        return None
    return {"id": row["id"], "username": row["username"], "role": row["role"]}


def _token_key():
    key = os.environ.get("VILA_AUTH_SECRET")
    if not key or len(key) < 32:
        raise RuntimeError(
            "Defina VILA_AUTH_SECRET com pelo menos 32 caracteres antes de iniciar a API"
        )
    return key.encode("utf-8")


def issue_token(user):
    now = int(time.time())
    payload = {
        "sub": user["id"], "username": user["username"],
        "iat": now, "exp": now + TOKEN_TTL_SECONDS,
    }
    body = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode()
    ).rstrip(b"=")
    signature = hmac.new(_token_key(), body, hashlib.sha256).digest()
    return (body + b"." + base64.urlsafe_b64encode(signature).rstrip(b"=")).decode()


def resolve_token(db_path, token):
    try:
        body, signature = token.encode().split(b".", 1)
        expected = hmac.new(_token_key(), body, hashlib.sha256).digest()
        supplied = base64.urlsafe_b64decode(signature + b"=" * (-len(signature) % 4))
        if not hmac.compare_digest(expected, supplied):
            return None
        payload = json.loads(base64.urlsafe_b64decode(body + b"=" * (-len(body) % 4)))
        if int(payload["exp"]) <= int(time.time()):
            return None
        with _connect(db_path) as conn:
            row = conn.execute(
                "SELECT id,username,role FROM operators WHERE id=? AND active=1",
                (int(payload["sub"]),),
            ).fetchone()
        return dict(row) if row else None
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, RuntimeError):
        return None
