
"""Rotas da API central."""

from typing import Optional

from fastapi import APIRouter, Body, HTTPException, Query, Request

from central import db

router = APIRouter()

LIMIT = Query(100, ge=1, le=1000, description="Máximo de registros")
OFFSET = Query(0, ge=0, description="Registros a pular")


def _path(request: Request):
    return request.app.state.db_path


@router.get("/health")
def health(request: Request):
    db.check_db(_path(request))
    return {"status": "ok"}


@router.get("/api/spaces")
def spaces(request: Request):
    return db.list_spaces(_path(request))


@router.get("/api/spaces/{space_id}")
def space(space_id: str, request: Request):
    return db.get_space(_path(request), space_id)


@router.get("/api/devices")
def devices(
    request: Request,
    space_id: Optional[str] = Query(None, max_length=64),
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
):
    return db.query_telemetry(
        _path(request), space_id, device_id, metric, limit, offset
    )


@router.get("/api/alerts")
def alerts(
    request: Request,
    space_id: Optional[str] = Query(None, max_length=64),
    severity: Optional[str] = Query(
        None, pattern="^(info|warning|critical)$"
    ),
    resolved: Optional[bool] = None,
    limit: int = LIMIT,
    offset: int = OFFSET,
):
    return db.list_alerts(
        _path(request), space_id, severity, resolved, limit, offset
    )


@router.get("/api/status")
def status(request: Request):
    return db.get_status(_path(request))


@router.post("/api/sync/{agent_id}")
def sync_telemetry(
    agent_id: str,
    request: Request,
    payload: dict = Body(...),
):
    """Recebe um lote de leituras pendentes de um agente."""

    readings = payload.get("readings")

    if not isinstance(readings, list):
        raise HTTPException(
            status_code=400,
            detail="O campo readings deve ser uma lista",
        )

    try:
        result = db.receive_telemetry_batch(
            _path(request),
            agent_id,
            readings,
        )
    except (ValueError, db.NotFoundError) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return {
        "status": "ok",
        "agent_id": agent_id,
        **result,
    }
