from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_cliente
from app.schemas.quejas import QuejaIn, QuejaOut
from app.services import quejas as quejas_service

router = APIRouter(prefix="/quejas", tags=["quejas"])


@router.post("", response_model=QuejaOut, status_code=status.HTTP_201_CREATED)
def crear(datos: QuejaIn, db: Session = Depends(get_db), cliente_id: int = Depends(require_cliente)):
    return quejas_service.crear(db, cliente_id, datos)


@router.get("", response_model=list[QuejaOut])
def listar(db: Session = Depends(get_db), cliente_id: int = Depends(require_cliente)):
    return quejas_service.listar(db, cliente_id)
