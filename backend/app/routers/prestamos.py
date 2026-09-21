from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import UsuarioActual, get_current_user, require_cliente
from app.schemas.prestamos import PrestamoOut, SolicitudPrestamoIn
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
