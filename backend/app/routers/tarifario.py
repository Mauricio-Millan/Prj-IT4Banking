from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import Tarifa
from app.schemas.tarifario import TarifaOut, TarifarioOut

router = APIRouter(prefix="/tarifario", tags=["tarifario"])


@router.get("", response_model=TarifarioOut)
def obtener(db: Session = Depends(get_db)):
    """Publico, sin JWT: transparencia SBS. Solo tarifas activas (V1); TRF-INTER (inactiva) no aparece."""
    tarifas = db.scalars(select(Tarifa).where(Tarifa.activa == True).order_by(Tarifa.codigo)).all()  # noqa: E712 (.is_(True) compila a "IS 1", invalido en T-SQL)
    return TarifarioOut(tarifas=[TarifaOut.model_validate(t) for t in tarifas])
