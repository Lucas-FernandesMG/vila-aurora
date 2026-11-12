"""API central FastAPI. Execução: uvicorn central.main:app"""
import sqlite3
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from central import db
from central.routes import router


def create_app(db_path=None):
    """Cria a aplicação. O banco é criado automaticamente na inicialização."""
    path = db_path or db.DEFAULT_DB_PATH

    @asynccontextmanager
    async def lifespan(app):
        db.init_db(path)
        yield

    app = FastAPI(title="Rede Comunitária Vila Aurora - API Central", version="0.1.0",
                  lifespan=lifespan)
    app.state.db_path = path
    app.include_router(router)

    @app.exception_handler(db.NotFoundError)
    async def not_found_handler(request: Request, exc: db.NotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(sqlite3.Error)
    async def sqlite_error_handler(request: Request, exc: sqlite3.Error):
        return JSONResponse(status_code=503, content={"detail": "Banco de dados indisponível"})

    return app


app = create_app()
