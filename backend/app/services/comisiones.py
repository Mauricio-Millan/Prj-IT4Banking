"""HU-Tarifario-Comisiones: calculo y cobro de comisiones. Los eventos que efectivamente
cobran hoy son 'retiro' (RET-RED, desde services/transacciones.py) y 'pago_cuota_vencida'
(PRE-ATR, desde services/prestamos.py); el resto del catalogo (TRF-INTRA, MAN-CTA, TAR-EMI,
TRF-INTER) solo existe para el tarifario publico — comision 0 siempre porque nunca se llama
calcular()/cobrar() para esos eventos (V5), no porque el codigo lo compruebe caso por caso.
"""
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import SaldoInsuficiente
from app.models import MovimientoContable, Tarifa, Transaccion
from app.models.contabilidad import CODIGO_DEPOSITOS_VISTA, CODIGO_INGRESOS_COMISION
from app.services.contabilidad import cuenta_contable_id, debitar, registrar_asiento


class SaldoInsuficienteComision(Exception):
    def __init__(self, mensaje: str):
        self.mensaje = mensaje
        super().__init__(mensaje)


def calcular(db: Session, evento: str, cuenta_id: int, fecha: date) -> tuple[Tarifa | None, Decimal]:
    """Tarifa aplicable y el monto (0 si no aplica, esta inactiva, aun no vigente, o si todavia
    hay cuota gratis este mes calendario)."""
    tarifa = db.scalar(select(Tarifa).where(
        Tarifa.evento == evento, Tarifa.activa == True, Tarifa.vigente_desde <= fecha,  # noqa: E712 (.is_(True) -> "IS 1", invalido en T-SQL)
    ))
    if tarifa is None:
        return None, Decimal("0.00")

    if tarifa.gratis_por_mes is not None:
        # Hoy solo RET-RED tiene cuota gratuita, y se cuenta sobre retiros aplicados de la
        # cuenta en el mes calendario (no sobre "eventos" genericos): ver HU V4.
        desde = datetime(fecha.year, fecha.month, 1, tzinfo=timezone.utc)
        hasta = (datetime(fecha.year + 1, 1, 1, tzinfo=timezone.utc) if fecha.month == 12
                 else datetime(fecha.year, fecha.month + 1, 1, tzinfo=timezone.utc))
        usados = db.scalar(
            select(func.count()).select_from(Transaccion).where(
                Transaccion.cuenta_origen_id == cuenta_id, Transaccion.tipo == "retiro",
                Transaccion.estado == "aplicada", Transaccion.fecha_hora >= desde, Transaccion.fecha_hora < hasta,
            )
        )
        if usados < tarifa.gratis_por_mes:
            return tarifa, Decimal("0.00")

    return tarifa, tarifa.monto


def cobrar(
    db: Session, tarifa: Tarifa, cuenta_id: int, moneda: str, transaccion_origen_id: int, concepto: str,
    mensaje_error: str | None = None,
) -> Transaccion:
    """debitar (guardia atomica) + Transaccion(tipo='comision', canal='sistema') + asiento
    DEBE 2101 (cuenta cliente) / HABER 4101. Mismo commit que la operacion que la origino:
    si la cuenta cubre la operacion pero no la comision, todo se revierte (V3)."""
    try:
        debitar(db, cuenta_id, tarifa.monto)
    except SaldoInsuficiente:
        raise SaldoInsuficienteComision(mensaje_error or f"Saldo insuficiente para cubrir la comisión de S/ {tarifa.monto:.2f}")

    transaccion = Transaccion(
        cuenta_origen_id=cuenta_id, tipo="comision", monto=tarifa.monto, canal="sistema",
        estado="aplicada", concepto=concepto, transaccion_origen_id=transaccion_origen_id,
    )
    db.add(transaccion)
    db.flush()

    depositos_id = cuenta_contable_id(db, CODIGO_DEPOSITOS_VISTA)
    ingresos_id = cuenta_contable_id(db, CODIGO_INGRESOS_COMISION)
    movs = [
        MovimientoContable(cuenta_contable_id=depositos_id, cuenta_cliente_id=cuenta_id,
                            tipo_movimiento="D", importe=tarifa.monto, moneda=moneda),
        MovimientoContable(cuenta_contable_id=ingresos_id, cuenta_cliente_id=None,
                            tipo_movimiento="H", importe=tarifa.monto, moneda=moneda),
    ]
    registrar_asiento(db, "comision", transaccion.transaccion_id, movs)
    return transaccion
