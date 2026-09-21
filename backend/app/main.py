from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.exceptions import RecursoNoEncontrado, SaldoInsuficiente
from app.routers import auth, backoffice, cuentas, prestamos, quejas, tarjetas, transacciones

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(cuentas.router)
app.include_router(tarjetas.router)
app.include_router(prestamos.router)
app.include_router(transacciones.router)
app.include_router(quejas.router)
app.include_router(backoffice.router)


@app.exception_handler(RecursoNoEncontrado)
def _recurso_no_encontrado(request: Request, exc: RecursoNoEncontrado):
    return JSONResponse(status_code=404, content={"detail": "Recurso no encontrado"})


@app.exception_handler(SaldoInsuficiente)
def _saldo_insuficiente(request: Request, exc: SaldoInsuficiente):
    return JSONResponse(status_code=422, content={"detail": "Saldo insuficiente"})


@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "env": settings.env}
