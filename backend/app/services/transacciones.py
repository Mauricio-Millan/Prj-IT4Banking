from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import RecursoNoEncontrado
from app.models import AuditLog, Cuenta, MovimientoContable, Transaccion
from app.models.contabilidad import CODIGO_CAJA, CODIGO_DEPOSITOS_VISTA
from app.schemas.transacciones import TransaccionIn
from app.services import comisiones as comisiones_service
from app.services.contabilidad import acreditar, cuenta_contable_id, debitar, registrar_asiento, verificar_balance  # noqa: F401 (verificar_balance re-exportado: ver tests/test_libro_mayor.py)


class MonedaIncompatible(Exception):
    pass


def _registrar_asiento_operacion(
    db: Session, tipo_operacion: str, transaccion_id: int, monto: Decimal, moneda: str,
    cuenta_cliente_debe: int | None, cuenta_cliente_haber: int | None,
) -> None:
    """Arma el asiento de 2 lineas de deposito/retiro/transferencia. La convencion contable
    es fija por tipo:
    deposito       -> DEBE Caja                 / HABER Depositos a la vista (cliente destino)
    retiro         -> DEBE Depositos a la vista (cliente origen) / HABER Caja
    transferencia  -> DEBE Depositos a la vista (origen) / HABER Depositos a la vista (destino)"""
    caja_id = None
    depositos_id = None
    if tipo_operacion in ("deposito", "retiro"):
        caja_id = cuenta_contable_id(db, CODIGO_CAJA)
    if cuenta_cliente_debe is not None or cuenta_cliente_haber is not None:
        depositos_id = cuenta_contable_id(db, CODIGO_DEPOSITOS_VISTA)

    if tipo_operacion == "deposito":
        movs = [
            MovimientoContable(cuenta_contable_id=caja_id, cuenta_cliente_id=None,
                                tipo_movimiento="D", importe=monto, moneda=moneda),
            MovimientoContable(cuenta_contable_id=depositos_id, cuenta_cliente_id=cuenta_cliente_haber,
                                tipo_movimiento="H", importe=monto, moneda=moneda),
        ]
    elif tipo_operacion == "retiro":
        movs = [
            MovimientoContable(cuenta_contable_id=depositos_id, cuenta_cliente_id=cuenta_cliente_debe,
                                tipo_movimiento="D", importe=monto, moneda=moneda),
            MovimientoContable(cuenta_contable_id=caja_id, cuenta_cliente_id=None,
                                tipo_movimiento="H", importe=monto, moneda=moneda),
        ]
    else:  # transferencia
        movs = [
            MovimientoContable(cuenta_contable_id=depositos_id, cuenta_cliente_id=cuenta_cliente_debe,
                                tipo_movimiento="D", importe=monto, moneda=moneda),
            MovimientoContable(cuenta_contable_id=depositos_id, cuenta_cliente_id=cuenta_cliente_haber,
                                tipo_movimiento="H", importe=monto, moneda=moneda),
        ]
    registrar_asiento(db, tipo_operacion, transaccion_id, movs)


def _resolver_destino(db: Session, valor: str) -> Cuenta | None:
    """valor ya viene validado por Pydantic (14 = numero_cuenta, 20 = cci, DV correcto)."""
    return db.scalar(select(Cuenta).where(
        or_(Cuenta.numero_cuenta == valor, Cuenta.cci == valor), Cuenta.estado == "activa",
    ))


def retiros_este_mes(db: Session, cuenta_id: int, hoy) -> int:
    """Publica: routers/cuentas.py la reusa para GET /cuentas/{id}/comision-retiro."""
    desde = datetime(hoy.year, hoy.month, 1, tzinfo=timezone.utc)
    hasta = (datetime(hoy.year + 1, 1, 1, tzinfo=timezone.utc) if hoy.month == 12
             else datetime(hoy.year, hoy.month + 1, 1, tzinfo=timezone.utc))
    return db.scalar(
        select(func.count()).select_from(Transaccion).where(
            Transaccion.cuenta_origen_id == cuenta_id, Transaccion.tipo == "retiro",
            Transaccion.estado == "aplicada", Transaccion.fecha_hora >= desde, Transaccion.fecha_hora < hasta,
        )
    )


def crear(db: Session, cliente_id: int, usuario_id: int, datos: TransaccionIn, ip: str | None = None) -> dict:
    """RF-08: deposito/retiro/transferencia. Atomico: si algo falla antes del commit, nada se
    persiste (ni el UPDATE de saldo, ni la transaccion, ni el asiento, ni la comision).
    canal: 'cajero'/'agente' para deposito/retiro (obligatorio, HU-Tarifario-Comisiones);
    'web' fijo para transferencia (ver TransaccionIn)."""
    origen_id = destino_id = None
    hoy = datetime.now(timezone.utc).date()
    # Datos para cobrar RET-RED, calculados ANTES de insertar la transaccion de este retiro:
    # si se calcularan despues, la cuenta "se contaria a si misma" como uno de los 3 gratis.
    cuenta_para_comision = None
    tarifa_comision = None
    monto_comision = Decimal("0.00")
    retiros_previos = 0

    if datos.tipo == "deposito":
        # el cliente solo deposita en cuentas propias: no basta con acertar el numero de otra persona
        destino = db.scalar(select(Cuenta).where(
            or_(Cuenta.numero_cuenta == datos.cuenta_destino, Cuenta.cci == datos.cuenta_destino),
            Cuenta.cliente_id == cliente_id,
        ))
        if destino is None:
            raise RecursoNoEncontrado()
        acreditar(db, destino.cuenta_id, datos.monto)
        destino_id, moneda = destino.cuenta_id, destino.moneda

    elif datos.tipo == "retiro":
        origen = db.scalar(select(Cuenta).where(Cuenta.cuenta_id == datos.cuenta_origen_id, Cuenta.cliente_id == cliente_id))
        if origen is None:
            raise RecursoNoEncontrado()
        retiros_previos = retiros_este_mes(db, origen.cuenta_id, hoy)
        tarifa_comision, monto_comision = comisiones_service.calcular(db, "retiro", origen.cuenta_id, hoy)
        debitar(db, origen.cuenta_id, datos.monto)
        origen_id, moneda = origen.cuenta_id, origen.moneda
        cuenta_para_comision = origen.cuenta_id

    else:  # transferencia
        origen = db.scalar(select(Cuenta).where(Cuenta.cuenta_id == datos.cuenta_origen_id, Cuenta.cliente_id == cliente_id))
        destino = _resolver_destino(db, datos.cuenta_destino)
        if origen is None or destino is None:
            raise RecursoNoEncontrado()
        if origen.cuenta_id == destino.cuenta_id:
            raise RecursoNoEncontrado()  # transferirse a si mismo por CCI/numero propio: mismo mensaje, sin filtrar
        if origen.moneda != destino.moneda:
            # ponytail: sin fuente de tipo de cambio en esta app; se rechaza en vez de convertir.
            raise MonedaIncompatible()
        debitar(db, origen.cuenta_id, datos.monto)
        acreditar(db, destino.cuenta_id, datos.monto)
        origen_id, destino_id, moneda = origen.cuenta_id, destino.cuenta_id, origen.moneda

    transaccion = Transaccion(
        cuenta_origen_id=origen_id, cuenta_destino_id=destino_id,
        tipo=datos.tipo, monto=datos.monto, canal=(datos.canal or "web"), estado="aplicada",
    )
    db.add(transaccion)
    db.flush()  # obtiene transaccion_id

    _registrar_asiento_operacion(
        db, datos.tipo, transaccion.transaccion_id, datos.monto, moneda,
        cuenta_cliente_debe=origen_id, cuenta_cliente_haber=destino_id,
    )

    comision = None
    if cuenta_para_comision is not None and monto_comision > 0:
        concepto = f"Comisión: retiro en red aliada ({retiros_previos + 1}.º del mes)"
        mensaje_error = f"Saldo insuficiente para el retiro más la comisión de S/ {tarifa_comision.monto:.2f}"
        comisiones_service.cobrar(db, tarifa_comision, cuenta_para_comision, moneda,
                                   transaccion.transaccion_id, concepto, mensaje_error)
        comision = {"monto": monto_comision, "concepto": concepto}

    db.add(AuditLog(usuario_id=usuario_id, accion="crear", entidad="transaccion",
                     entidad_id=str(transaccion.transaccion_id), ip=ip))
    db.commit()
    db.refresh(transaccion)
    return {"transaccion": transaccion, "comision": comision}
