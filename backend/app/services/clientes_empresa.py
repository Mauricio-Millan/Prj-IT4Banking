import secrets
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.numeracion import cci_de
from app.core.security import hash_password
from app.models import AuditLog, Cliente, Cuenta, Usuario
from app.schemas.clientes_empresa import ClienteEmpresaIn
from app.services import tarjetas as tarjetas_service
from app.services.onboarding import codigo_cliente_disponible, numero_cuenta_disponible


class RucDuplicado(Exception):
    pass


class EmailDuplicado(Exception):
    pass


def crear(db: Session, datos: ClienteEmpresaIn, admin_id: int, ip: str | None = None) -> dict:
    """V6: cliente, usuario, cuenta y tarjeta se confirman juntos o nada se persiste — mismo
    patron que onboarding.registrar()."""
    if db.scalar(select(Cliente.cliente_id).where(
        Cliente.tipo_documento == "RUC", Cliente.numero_documento == datos.ruc,
    )):
        raise RucDuplicado()
    if db.scalar(select(Usuario.usuario_id).where(Usuario.email == datos.email)):
        raise EmailDuplicado()

    cliente = Cliente(
        codigo_cliente=codigo_cliente_disponible(db),
        tipo_documento="RUC",
        numero_documento=datos.ruc,
        razon_social=datos.razon_social,
        # el representante es quien inicia sesion, no la empresa (ver models/cliente.py).
        nombres=datos.representante_nombres,
        apellidos=datos.representante_apellidos,
        # placeholder: RUC no tiene fecha de nacimiento; nunca se usa en un calculo porque
        # reevaluar_segmento retorna antes para 'empresa' (V8).
        fecha_nacimiento=date.today(),
        email=datos.email,
        telefono=datos.telefono,
        region=datos.region,
        segmento="empresa",
    )
    password_temporal = secrets.token_urlsafe(12)  # V7: obliga a cambiarla en el primer acceso
    usuario = Usuario(cliente=cliente, email=datos.email, password_hash=hash_password(password_temporal),
                       rol="cliente", debe_cambiar_password=True)
    numero_cuenta = numero_cuenta_disponible(db, "PEN")
    cuenta = Cuenta(
        cliente=cliente, tipo_cuenta="corriente", moneda="PEN", saldo=0,  # V5: corriente, nunca ahorro
        numero_cuenta=numero_cuenta, cci=cci_de(numero_cuenta),
    )
    db.add_all([cliente, usuario, cuenta])
    db.flush()  # asigna cuenta_id: lo usa emitir() como AAD del cifrado del PAN

    tarjeta = tarjetas_service.emitir(db, cuenta)
    db.add(tarjeta)
    db.flush()
    db.add(AuditLog(usuario_id=admin_id, accion="crear_cliente_empresa", entidad="cliente",
                     entidad_id=str(cliente.cliente_id), ip=ip))
    db.commit()
    db.refresh(cliente)
    db.refresh(cuenta)
    db.refresh(tarjeta)
    return {"cliente": cliente, "cuenta": cuenta, "tarjeta": tarjeta, "password_temporal": password_temporal}


def listar(db: Session) -> list[Cliente]:
    """Sin filtro de busqueda libre (coherente con V14 de HU-Gestion-Usuarios-Internos-Backoffice):
    es un registro de lo que el propio banco creo, no una busqueda de clientes."""
    return list(db.scalars(select(Cliente).where(Cliente.tipo_documento == "RUC").order_by(Cliente.cliente_id)))
