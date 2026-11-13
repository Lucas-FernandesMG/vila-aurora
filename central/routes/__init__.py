"""Rotas da API central."""
from typing import Optional

from fastapi.responses import HTMLResponse
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from central.mtls import require_agent_certificate

from central import auth, db
from central.analytics import detect_anomalies
from central.dashboard import dashboard_response
from central.security import current_operator, require_roles

router = APIRouter()
LIMIT = Query(100, ge=1, le=1000, description="Máximo de registros")
OFFSET = Query(0, ge=0, description="Registros a pular")


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=1, max_length=256)
    totp_code: str = Field(pattern=r"^\d{6}$")


class OperatorCreateRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=12, max_length=256)
    role: str = Field(pattern=r"^(admin|operator|auditor)$")


def _path(request: Request):
    return request.app.state.db_path


@router.post("/api/auth/login")
def login(payload: LoginRequest, request: Request):
    user = auth.authenticate(
        _path(request), payload.username, payload.password, payload.totp_code
    )
    if user is None:
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    return {
        "access_token": auth.issue_token(user),
        "token_type": "bearer",
        "expires_in": auth.TOKEN_TTL_SECONDS,
        "user": user,
    }


@router.get("/api/auth/me")
def who_am_i(user=Depends(current_operator)):
    return user


@router.post("/api/operators", status_code=201)
def create_operator(
    payload: OperatorCreateRequest,
    request: Request,
    _admin=Depends(require_roles("admin")),
):
    try:
        secret = auth.create_operator(
            _path(request), payload.username, payload.password, payload.role
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        # Não expõe detalhes de banco, índices ou SQL ao cliente.
        if "UNIQUE constraint failed" in str(exc):
            raise HTTPException(status_code=409, detail="Usuário já existe") from exc
        raise
    return {
        "username": payload.username,
        "role": payload.role,
        "totp_secret": secret,
        "provisioning_uri": auth.provisioning_uri(payload.username, secret),
        "message": "Cadastre o segredo no aplicativo autenticador. Ele não será exibido novamente.",
    }


@router.get("/health")
def health(request: Request):
    db.check_db(_path(request))
    return {"status": "ok"}


@router.get("/api/spaces")
def spaces(request: Request, _user=Depends(current_operator)):
    return db.list_spaces(_path(request))


@router.get("/api/spaces/{space_id}")
def space(space_id: str, request: Request, _user=Depends(current_operator)):
    return db.get_space(_path(request), space_id)


@router.get("/api/devices")
def devices(
    request: Request,
    space_id: Optional[str] = Query(None, max_length=64),
    _user=Depends(current_operator),
):
    return db.list_devices(_path(request), space_id)


@router.get("/api/telemetry")
def telemetry(
    request: Request,
    space_id: Optional[str] = Query(None, max_length=64),
    device_id: Optional[str] = Query(None, max_length=64),
    metric: Optional[str] = Query(None, max_length=64),
    limit: int = LIMIT,
    offset: int = OFFSET,
    _user=Depends(current_operator),
):
    return db.query_telemetry(_path(request), space_id, device_id, metric, limit, offset)


@router.get("/api/alerts")
def alerts(
    request: Request,
    space_id: Optional[str] = Query(None, max_length=64),
    severity: Optional[str] = Query(None, pattern="^(info|warning|critical)$"),
    resolved: Optional[bool] = None,
    limit: int = LIMIT,
    offset: int = OFFSET,
    _user=Depends(current_operator),
):
    return db.list_alerts(_path(request), space_id, severity, resolved, limit, offset)


@router.get("/api/status")
def status(request: Request, _user=Depends(current_operator)):
    return db.get_status(_path(request))


@router.post("/api/sync/{agent_id}")
def sync_telemetry(
    agent_id: str,
    request: Request,
    payload: dict = Body(...),
    authenticated_agent: str = Depends(require_agent_certificate),
):
    """Sincronizacao autenticada por certificado mTLS."""
    if authenticated_agent != agent_id:
        raise HTTPException(
            status_code=403,
            detail="Identidade de agente incompativel",
        )

    readings = payload.get("readings")
    if not isinstance(readings, list):
        raise HTTPException(
            status_code=400,
            detail="O campo readings deve ser uma lista",
        )

    try:
        result = db.receive_telemetry_batch(
            _path(request),
            authenticated_agent,
            readings,
        )
    except (ValueError, db.NotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "status": "ok",
        "agent_id": authenticated_agent,
        **result,
    }

@router.get("/api/anomalies")
def anomalies(
    request: Request,
    metric: str = Query(..., min_length=1, max_length=64),
    limit: int = Query(1000, ge=8, le=1000),
    _user=Depends(current_operator),
):
    """Analisa leituras de uma m?trica e identifica valores at?picos."""
    readings = db.query_telemetry(
        _path(request),
        metric=metric,
        limit=limit,
        offset=0,
    )
    return detect_anomalies(readings)


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return dashboard_response()
