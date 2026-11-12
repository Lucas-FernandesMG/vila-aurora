"""Dependências de autorização RBAC para as rotas da API."""
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from central import auth

_bearer = HTTPBearer(auto_error=False)


def current_operator(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
):
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Autenticação necessária")
    user = auth.resolve_token(request.app.state.db_path, credentials.credentials)
    if user is None:
        raise HTTPException(status_code=401, detail="Sessão inválida ou expirada")
    return user


def require_roles(*roles):
    def dependency(user=Depends(current_operator)):
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Permissão insuficiente")
        return user
    return dependency
