"""Autenticacao da identidade dos agentes via mTLS."""
import re

from fastapi import HTTPException, Request


def require_agent_certificate(request: Request, agent_id: str) -> str:
    extensions = request.scope.get("extensions") or {}
    tls = extensions.get("tls")

    if not isinstance(tls, dict):
        raise HTTPException(status_code=401, detail="Conexao TLS obrigatoria")

    if tls.get("client_cert_error"):
        raise HTTPException(status_code=401, detail="Certificado de cliente ausente ou invalido")

    chain = tls.get("client_cert_chain") or []
    if not chain:
        raise HTTPException(status_code=401, detail="Certificado de cliente ausente")

    subject = tls.get("client_cert_name") or ""
    match = re.search(r"(?:^|,)CN=([^,]+)", subject)

    if not match:
        raise HTTPException(status_code=401, detail="CN do certificado nao encontrado")

    certificate_agent = match.group(1).strip()

    if certificate_agent != agent_id:
        raise HTTPException(
            status_code=403,
            detail="O certificado nao pertence ao agente informado",
        )

    return certificate_agent
