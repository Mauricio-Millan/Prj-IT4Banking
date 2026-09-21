from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import UsuarioActual, get_current_user, require_cliente
from app.schemas.transacciones import TransaccionIn, TransaccionOut
from app.services import transacciones as transacciones_service

router = APIRouter(prefix="/transacciones", tags=["transacciones"])


@router.post("", response_model=TransaccionOut, status_code=status.HTTP_201_CREATED)
def crear(
    datos: TransaccionIn,
    request: Request,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
    cliente_id: int = Depends(require_cliente),
):
    try:
        return transacciones_service.crear(
            db, cliente_id, usuario.usuario_id, datos, ip=request.client.host if request.client else None
        )
    except transacciones_service.MonedaIncompatible:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Las cuentas deben tener la misma moneda")
