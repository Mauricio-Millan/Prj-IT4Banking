from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import UsuarioActual, get_current_user, require_cliente
from app.schemas.prestamos import CuotaOut, PagoOut, PagoPrestamoIn, PrestamoOut, SolicitudPrestamoIn
from app.services import comisiones as comisiones_service
from app.services import prestamos as prestamos_service

router = APIRouter(prefix="/prestamos", tags=["prestamos"])


@router.post("/solicitudes", response_model=PrestamoOut, status_code=status.HTTP_201_CREATED)
def solicitar(
    datos: SolicitudPrestamoIn,
    request: Request,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
    cliente_id: int = Depends(require_cliente),
):
    p = prestamos_service.solicitar(db, cliente_id, usuario.usuario_id, datos,
                                     ip=request.client.host if request.client else None)
    return prestamos_service.a_schema(p)


@router.get("", response_model=list[PrestamoOut])
def listar(db: Session = Depends(get_db), cliente_id: int = Depends(require_cliente)):
    return [prestamos_service.a_schema(p) for p in prestamos_service.listar(db, cliente_id)]


@router.get("/{prestamo_id}/cronograma", response_model=list[CuotaOut])
def cronograma(prestamo_id: int, db: Session = Depends(get_db), cliente_id: int = Depends(require_cliente)):
    return prestamos_service.cronograma(db, cliente_id, prestamo_id)


@router.post("/{prestamo_id}/pagos", response_model=PagoOut, status_code=status.HTTP_201_CREATED)
def pagar(
    prestamo_id: int,
    datos: PagoPrestamoIn,
    request: Request,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
    cliente_id: int = Depends(require_cliente),
):
    try:
        return prestamos_service.pagar_cuota(
            db, prestamo_id, cliente_id, usuario.usuario_id, datos.cuenta_origen_id,
            ip=request.client.host if request.client else None,
        )
    except prestamos_service.PrestamoNoVigente:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="El préstamo no tiene cuotas pendientes por pagar")
    except comisiones_service.SaldoInsuficienteComision as e:
        # El pago de la cuota (primer debito) ya se aplico antes de que fallara la penalidad:
        # sin este rollback explicito esa escritura queda pendiente en la sesion (V4/V3).
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.mensaje)
