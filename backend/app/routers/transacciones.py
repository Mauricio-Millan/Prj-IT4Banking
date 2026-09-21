from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import UsuarioActual, get_current_user, require_cliente
from app.schemas.transacciones import ComisionOut, TransaccionIn, TransaccionOut
from app.services import comisiones as comisiones_service
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
        resultado = transacciones_service.crear(
            db, cliente_id, usuario.usuario_id, datos, ip=request.client.host if request.client else None
        )
    except transacciones_service.MonedaIncompatible:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Las cuentas deben tener la misma moneda")
    except comisiones_service.SaldoInsuficienteComision as e:
        # El retiro (primer debito) ya se aplico en esta misma sesion antes de que fallara el
        # de la comision: sin este rollback explicito, esa escritura queda pendiente y visible
        # dentro de la transaccion hasta que algo mas la cierre (V3 exige que "todo se revierta").
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.mensaje)

    transaccion = resultado["transaccion"]
    comision = ComisionOut(**resultado["comision"]) if resultado["comision"] else None
    return TransaccionOut(
        transaccion_id=transaccion.transaccion_id, fecha_hora=transaccion.fecha_hora, tipo=transaccion.tipo,
        monto=transaccion.monto, canal=transaccion.canal, estado=transaccion.estado, concepto=transaccion.concepto,
        cuenta_origen_id=transaccion.cuenta_origen_id, cuenta_destino_id=transaccion.cuenta_destino_id,
        comision=comision,
    )
