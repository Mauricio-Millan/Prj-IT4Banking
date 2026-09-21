from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import UsuarioActual, require_role
from app.schemas.prestamos import DecisionPrestamoIn, PrestamoOut, PrestamoRevisionOut
from app.services import prestamos as prestamos_service

# Separado de routers/prestamos.py a proposito: refleja la misma separacion que ya existe
# en el frontend (BackofficeLayout es un arbol de rutas aparte). Punto de crecimiento natural
# para /backoffice/quejas cuando se construya esa fase.
router = APIRouter(prefix="/backoffice", tags=["backoffice"])


@router.get("/prestamos", response_model=list[PrestamoRevisionOut])
def listar_pendientes(db: Session = Depends(get_db), _=Depends(require_role("analista", "admin"))):
    return prestamos_service.listar_pendientes(db)


@router.patch("/prestamos/{prestamo_id}", response_model=PrestamoOut)
def resolver(
    prestamo_id: int,
    datos: DecisionPrestamoIn,
    request: Request,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(require_role("analista", "admin")),
):
    try:
        p = prestamos_service.resolver(db, prestamo_id, datos.decision, usuario.usuario_id,
                                        ip=request.client.host if request.client else None)
    except prestamos_service.PrestamoYaResuelto:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="La solicitud ya fue resuelta")
    return prestamos_service.a_schema(p)
