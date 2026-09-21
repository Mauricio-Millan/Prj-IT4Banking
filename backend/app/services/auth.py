from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models import AuditLog, Usuario
from app.schemas.auth import LoginIn

LIMITE_INTENTOS_LOGIN = 5
VENTANA_INTENTOS_LOGIN = timedelta(minutes=15)


class CredencialesInvalidas(Exception):
    pass


class PasswordActualIncorrecta(Exception):
    pass


class PasswordInvalida(Exception):
    pass


def _login_bloqueado(db: Session, usuario_id: int) -> bool:
    """V16: mismo patron que el revelado de tarjeta (limite de intentos via audit_log),
    sin infraestructura de rate-limit nueva."""
    desde = datetime.now(timezone.utc) - VENTANA_INTENTOS_LOGIN
    return db.scalar(
        select(func.count()).select_from(AuditLog).where(
            AuditLog.usuario_id == usuario_id, AuditLog.accion == "login_fallido", AuditLog.fecha_hora >= desde,
        )
    ) >= LIMITE_INTENTOS_LOGIN


def autenticar(db: Session, datos: LoginIn, ip: str | None = None) -> Usuario:
    """RF-02: mismo mensaje/estado para email inexistente, password incorrecta, cuenta
    inactiva (V8) o bloqueo por intentos (V16) — anti-enumeracion en todos los casos."""
    usuario = db.scalar(select(Usuario).where(Usuario.email == datos.email.strip().lower()))

    if usuario and _login_bloqueado(db, usuario.usuario_id):
        db.add(AuditLog(usuario_id=usuario.usuario_id, accion="login_bloqueado", entidad="usuario",
                         entidad_id=str(usuario.usuario_id), ip=ip))
        db.commit()
        raise CredencialesInvalidas()

    if usuario is None or not usuario.activo or not verify_password(datos.password, usuario.password_hash):
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


def cambiar_password(db: Session, usuario_id: int, actual: str, nueva: str) -> None:
    """V11: exige la contrasena actual; minimo 12 caracteres para personal interno, 8 para
    clientes (igual que hoy). Apaga debe_cambiar_password, asi el analista/admin recuperan
    acceso al resto del backoffice en la siguiente peticion."""
    usuario = db.get(Usuario, usuario_id)
    if not verify_password(actual, usuario.password_hash):
        raise PasswordActualIncorrecta()

    minimo = 8 if usuario.rol == "cliente" else 12
    if len(nueva) < minimo:
        raise PasswordInvalida(f"La contraseña debe tener al menos {minimo} caracteres")

    usuario.password_hash = hash_password(nueva)
    usuario.debe_cambiar_password = False
    db.commit()
