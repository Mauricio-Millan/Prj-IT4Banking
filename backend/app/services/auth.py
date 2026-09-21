from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.models import AuditLog, Usuario
from app.schemas.auth import LoginIn


class CredencialesInvalidas(Exception):
    pass


def autenticar(db: Session, datos: LoginIn, ip: str | None = None) -> Usuario:
    """RF-02: mismo mensaje/estado para email inexistente o password incorrecta (anti-enumeracion)."""
    usuario = db.scalar(select(Usuario).where(Usuario.email == datos.email.strip().lower()))
    if usuario is None or not verify_password(datos.password, usuario.password_hash):
        db.add(AuditLog(
            usuario_id=usuario.usuario_id if usuario else None,
            accion="login_fallido",
            entidad="usuario",
            entidad_id=str(usuario.usuario_id) if usuario else None,
            ip=ip,
        ))
        db.commit()
        raise CredencialesInvalidas()

    usuario.ultimo_acceso = datetime.now(timezone.utc)
    db.add(AuditLog(usuario_id=usuario.usuario_id, accion="login", entidad="usuario",
                     entidad_id=str(usuario.usuario_id), ip=ip))
    db.commit()
    return usuario
