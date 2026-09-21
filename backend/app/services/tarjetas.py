import secrets
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import RecursoNoEncontrado
from app.core.numeracion import digito_verificador
from app.core.security import verify_password
from app.core.tarjetas_crypto import cifrar_pan, descifrar_pan, huella_pan
from app.models import AuditLog, Cuenta, Tarjeta, Usuario
from app.models.cuenta import fecha_vencimiento_tarjeta

LIMITE_INTENTOS = 5
VENTANA_INTENTOS = timedelta(minutes=15)


class CredencialesInvalidas(Exception):
    pass


class TarjetaNoActiva(Exception):
    pass


class DemasiadosIntentos(Exception):
    pass


def listar(db: Session, cliente_id: int) -> list[Tarjeta]:
    # Tarjeta no tiene cliente_id propio: se filtra por la cuenta que debita.
    return list(db.scalars(
        select(Tarjeta).join(Cuenta, Tarjeta.cuenta_id == Cuenta.cuenta_id).where(Cuenta.cliente_id == cliente_id)
    ))


def _generar_pan() -> str:
    """16 digitos: BIN (8) + 7 aleatorios + 1 DV Luhn. El BIN nunca sale del sistema:
    no hay red que lo enrute, es puramente demostrativo."""
    cuerpo = settings.tarjeta_bin + f"{secrets.randbelow(10**7):07d}"
    return cuerpo + digito_verificador(cuerpo)


def emitir(db: Session, cuenta: Cuenta) -> Tarjeta:
    """Requiere que `cuenta` ya tenga cuenta_id asignado (post-flush): es el AAD del cifrado
    del PAN, impide trasplantar el blob cifrado de una tarjeta a otra fila."""
    for _ in range(5):
        pan = _generar_pan()
        huella = huella_pan(pan)
        if not db.scalar(select(Tarjeta.tarjeta_id).where(Tarjeta.pan_hmac == huella)):
            break
    else:
        raise RuntimeError("No se pudo generar un PAN unico tras varios intentos")  # pragma: no cover

    hoy = date.today()
    return Tarjeta(
        cuenta=cuenta, tipo_tarjeta="debito", ultimos_4=pan[-4:],
        pan_cifrado=cifrar_pan(pan, cuenta.cuenta_id), pan_hmac=huella,
        fecha_emision=hoy, fecha_vencimiento=fecha_vencimiento_tarjeta(hoy), estado="activa",
    )


def _intentos_fallidos_recientes(db: Session, usuario_id: int) -> int:
    desde = datetime.now(timezone.utc) - VENTANA_INTENTOS
    return db.scalar(
        select(func.count()).select_from(AuditLog).where(
            AuditLog.usuario_id == usuario_id,
            AuditLog.accion == "revelar_tarjeta_fallido",
            AuditLog.fecha_hora >= desde,
        )
    )


def revelar(db: Session, cliente_id: int, usuario_id: int, tarjeta_id: int, password: str, ip: str | None) -> dict:
    """Orden obligatorio (HU-Tarjeta-Datos-Cifrados-Revelar): rate-limit -> contrasena ->
    pertenencia+estado -> descifrado. Cada paso deja o no rastro en audit_log, nunca el PAN/CVV."""
    if _intentos_fallidos_recientes(db, usuario_id) >= LIMITE_INTENTOS:
        raise DemasiadosIntentos()

    usuario = db.get(Usuario, usuario_id)
    if usuario is None or not verify_password(password, usuario.password_hash):
        db.add(AuditLog(usuario_id=usuario_id, accion="revelar_tarjeta_fallido",
                         entidad="tarjeta", entidad_id=str(tarjeta_id), ip=ip))
        db.commit()
        raise CredencialesInvalidas()

    tarjeta = db.scalar(
        select(Tarjeta).join(Cuenta, Tarjeta.cuenta_id == Cuenta.cuenta_id)
        .where(Tarjeta.tarjeta_id == tarjeta_id, Cuenta.cliente_id == cliente_id)
    )
    if tarjeta is None:
        raise RecursoNoEncontrado()
    if tarjeta.estado != "activa":
        raise TarjetaNoActiva()

    pan = descifrar_pan(tarjeta.pan_cifrado, tarjeta.cuenta_id)
    cvv = f"{secrets.randbelow(1000):03d}"  # CVV dinamico: nunca se almacena, cambia en cada revelado
    db.add(AuditLog(usuario_id=usuario_id, accion="revelar_tarjeta",
                     entidad="tarjeta", entidad_id=str(tarjeta_id), ip=ip))
    db.commit()

    titular = f"{tarjeta.cuenta.cliente.nombres} {tarjeta.cuenta.cliente.apellidos}".upper()
    return {"pan": pan, "vencimiento": tarjeta.fecha_vencimiento.strftime("%m/%y"), "cvv": cvv, "titular": titular}
