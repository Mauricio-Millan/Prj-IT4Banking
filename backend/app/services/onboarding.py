from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.numeracion import cci_de, generar_codigo_cliente, generar_numero_cuenta
from app.core.security import hash_password
from app.models import AuditLog, Cliente, Cuenta, Tarjeta, Usuario
from app.schemas.auth import RegistroIn
from app.services import tarjetas as tarjetas_service


class ClienteDuplicado(Exception):
    def __init__(self, campo: str):
        self.campo = campo


def segmento_por_edad(fecha_nacimiento: date) -> str:
    # ponytail: regla minima; premium/empresa los asigna el banco, no el onboarding
    hoy = date.today()
    edad = hoy.year - fecha_nacimiento.year - ((hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day))
    return "joven" if edad < 30 else "clasico"


def codigo_cliente_disponible(db: Session) -> str:
    for _ in range(5):
        codigo = generar_codigo_cliente()
        if not db.scalar(select(Cliente.cliente_id).where(Cliente.codigo_cliente == codigo)):
            return codigo
    raise RuntimeError("No se pudo generar un codigo_cliente unico tras varios intentos")  # pragma: no cover


def numero_cuenta_disponible(db: Session, moneda: str) -> str:
    for _ in range(5):
        numero = generar_numero_cuenta(moneda)
        if not db.scalar(select(Cuenta.cuenta_id).where(Cuenta.numero_cuenta == numero)):
            return numero
    raise RuntimeError("No se pudo generar un numero_cuenta unico tras varios intentos")  # pragma: no cover


def registrar(db: Session, datos: RegistroIn, ip: str | None = None) -> tuple[Cliente, Usuario, Cuenta, Tarjeta]:
    """RF-01: crea cliente + usuario + cuenta de ahorro + tarjeta de debito virtual en una sola transaccion."""
    # un pasaporte "12345678" y un DNI "12345678" son personas distintas: se valida el par
    # (tipo_documento, numero_documento), no numero_documento solo (HU-Numeracion-Bancaria).
    if db.scalar(select(Cliente.cliente_id).where(
        Cliente.tipo_documento == datos.tipo_documento, Cliente.numero_documento == datos.numero_documento,
    )):
        raise ClienteDuplicado("numero_documento")
    if db.scalar(select(Usuario.usuario_id).where(Usuario.email == datos.email)):
        raise ClienteDuplicado("email")

    cliente = Cliente(
        codigo_cliente=codigo_cliente_disponible(db),
        tipo_documento=datos.tipo_documento,
        numero_documento=datos.numero_documento,
        nombres=datos.nombres,
        apellidos=datos.apellidos,
        fecha_nacimiento=datos.fecha_nacimiento,
        email=datos.email,
        telefono=datos.telefono,
        region=datos.region,
        segmento=segmento_por_edad(datos.fecha_nacimiento),
    )
    usuario = Usuario(cliente=cliente, email=datos.email, password_hash=hash_password(datos.password), rol="cliente")
    numero_cuenta = numero_cuenta_disponible(db, "PEN")
    cuenta = Cuenta(
        cliente=cliente, tipo_cuenta="ahorro", moneda="PEN", saldo=0,
        numero_cuenta=numero_cuenta, cci=cci_de(numero_cuenta),
    )
    db.add_all([cliente, usuario, cuenta])
    db.flush()  # asigna cuenta_id: lo usa emitir() como AAD del cifrado del PAN

    tarjeta = tarjetas_service.emitir(db, cuenta)
    db.add(tarjeta)
    db.flush()
    db.add(AuditLog(usuario_id=usuario.usuario_id, accion="crear", entidad="cliente", entidad_id=str(cliente.cliente_id), ip=ip))
    db.commit()
    return cliente, usuario, cuenta, tarjeta
