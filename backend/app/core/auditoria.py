from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import UsuarioActual, get_current_user
from app.models import AuditLog


def auditar_consulta(entidad: str):
    """V17: toda consulta de backoffice deja rastro, no solo las mutaciones. Dependencia
    generica para agregar a cualquier GET /backoffice/*, junto al require_role de la ruta."""

    def _dep(request: Request, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)) -> None:
        db.add(AuditLog(usuario_id=usuario.usuario_id, accion="consultar", entidad=entidad,
                         ip=request.client.host if request.client else None))
        db.commit()

    return _dep
