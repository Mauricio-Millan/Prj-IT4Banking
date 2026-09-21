from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import RecursoNoEncontrado
from app.core.security import hash_password
from app.models import AuditLog, Cliente, Usuario
from app.schemas.usuarios_internos import ActualizarUsuarioInternoIn, UsuarioInternoIn

ROLES_INTERNOS = ("analista", "admin")


class EmailDuplicado(Exception):
    pass


class OperacionNoPermitida(Exception):
    def __init__(self, mensaje: str):
        self.mensaje = mensaje


def crear(db: Session, datos: UsuarioInternoIn, admin_id: int, ip: str | None = None) -> Usuario:
    if db.scalar(select(Usuario.usuario_id).where(Usuario.email == datos.email)):
        raise EmailDuplicado()

    usuario = Usuario(email=datos.email, password_hash=hash_password(datos.password_temporal),
                       rol=datos.rol, activo=True, debe_cambiar_password=True)
    db.add(usuario)
    db.flush()
    db.add(AuditLog(usuario_id=admin_id, accion="crear_usuario_interno", entidad="usuario",
                     entidad_id=str(usuario.usuario_id), ip=ip))
    db.commit()
    db.refresh(usuario)
    return usuario


def listar(db: Session) -> list[Usuario]:
    return list(db.scalars(
        select(Usuario).where(Usuario.rol.in_(ROLES_INTERNOS)).order_by(Usuario.usuario_id)
    ))


def _admins_activos_excepto(db: Session, usuario_id: int) -> int:
    return db.scalar(
        select(func.count()).select_from(Usuario).where(
            Usuario.rol == "admin", Usuario.activo.is_(True), Usuario.usuario_id != usuario_id,
        )
    )


def actualizar(db: Session, usuario_id: int, admin_actual_id: int, datos: ActualizarUsuarioInternoIn,
               ip: str | None = None) -> Usuario:
    usuario = db.get(Usuario, usuario_id)
    if usuario is None or usuario.rol not in ROLES_INTERNOS:
        raise RecursoNoEncontrado()

    acciones = []

    if datos.activo is not None and datos.activo != usuario.activo:
        if not datos.activo:
            # V9: ni auto-desactivarse ni dejar el banco sin ningun admin activo.
            if usuario_id == admin_actual_id:
                raise OperacionNoPermitida("No puedes desactivar tu propia cuenta")
            if usuario.rol == "admin" and _admins_activos_excepto(db, usuario_id) == 0:
                raise OperacionNoPermitida("No puedes desactivar al último administrador activo")
        usuario.activo = datos.activo
        acciones.append("activar_usuario_interno" if datos.activo else "desactivar_usuario_interno")

    if datos.rol is not None and datos.rol != usuario.rol:
        if usuario.rol == "admin" and datos.rol != "admin":
            if usuario_id == admin_actual_id:
                raise OperacionNoPermitida("No puedes quitarte a ti mismo el rol de administrador")
            if _admins_activos_excepto(db, usuario_id) == 0:
                raise OperacionNoPermitida("No puedes quitarle el rol al último administrador activo")
        usuario.rol = datos.rol
        acciones.append("cambiar_rol_usuario_interno")

    if datos.password_temporal is not None:
        usuario.password_hash = hash_password(datos.password_temporal)
        usuario.debe_cambiar_password = True
        acciones.append("resetear_password_usuario_interno")

    db.flush()
    for accion in acciones:
        db.add(AuditLog(usuario_id=admin_actual_id, accion=accion, entidad="usuario",
                         entidad_id=str(usuario_id), ip=ip))
    db.commit()
    db.refresh(usuario)
    return usuario


def marcar_es_empleado(db: Session, cliente_id: int, es_empleado: bool, admin_id: int, ip: str | None = None) -> None:
    """V13: marca el conflicto de interes para que prestamos/quejas_service exijan admin."""
    cliente = db.get(Cliente, cliente_id)
    if cliente is None:
        raise RecursoNoEncontrado()
    cliente.es_empleado = es_empleado
    db.flush()
    db.add(AuditLog(usuario_id=admin_id, accion="marcar_es_empleado", entidad="cliente",
                     entidad_id=str(cliente_id), ip=ip))
    db.commit()
