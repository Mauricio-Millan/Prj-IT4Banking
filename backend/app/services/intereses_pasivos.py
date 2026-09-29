"""HU-Gastos-Operativos-Intereses-Pasivos: devengo diario de interes pasivo sobre cuentas de
ahorro, invocado desde app/jobs/cierre_diario.py. Simplificacion deliberada: devengo y abono
el mismo dia (un banco real los separa) -- no se justifica un job mensual aparte para una sola
linea de calculo cuando ya existe uno diario."""
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import AsientoContable, Cuenta, MovimientoContable
from app.models.contabilidad import CODIGO_DEPOSITOS_VISTA, CODIGO_GASTO_INTERES_PASIVO
from app.services.contabilidad import acreditar, cuenta_contable_id, registrar_asiento


def _tasa_diaria(tea_pct: Decimal) -> Decimal:
    tea = tea_pct / 100
    # Convencion bancaria peruana: año de 360 dias (misma que ya usa el devengo de intereses
    # activos en services/prestamos.py, salvo que ahi es mensual/30 y aqui es diario/360).
    return (1 + tea) ** (Decimal(1) / 360) - 1


def _ya_devengado(db: Session, cuenta_id: int, fecha: date) -> bool:
    """Idempotencia: sin este chequeo, correr cierre_diario dos veces para la misma fecha
    duplicaria el interes de ese dia (a diferencia de recalcular_mora/reevaluar_segmento, que
    se derivan siempre del estado actual, este paso SI acumula saldo con cada llamada)."""
    return db.scalar(
        select(MovimientoContable.movimiento_id)
        .join(AsientoContable, AsientoContable.asiento_id == MovimientoContable.asiento_id)
        .where(
            AsientoContable.tipo_operacion == "interes_pasivo", AsientoContable.fecha_contable == fecha,
            MovimientoContable.cuenta_cliente_id == cuenta_id,
        )
        .limit(1)
    ) is not None


def devengar_interes_pasivo(db: Session, cuenta: Cuenta, fecha: date) -> None:
    """V1: solo ahorro activa. V2: sin asiento si el interes redondea a 0.00. V3: se acredita
    y se registra el asiento en la misma llamada -- nunca uno sin el otro."""
    if cuenta.tipo_cuenta != "ahorro" or cuenta.estado != "activa" or cuenta.saldo <= 0:
        return
    if _ya_devengado(db, cuenta.cuenta_id, fecha):
        return

    interes = (cuenta.saldo * _tasa_diaria(settings.tea_pasiva_ahorro)).quantize(Decimal("0.01"))
    if interes <= 0:
        return

    acreditar(db, cuenta.cuenta_id, interes)

    gasto_id = cuenta_contable_id(db, CODIGO_GASTO_INTERES_PASIVO)
    depositos_id = cuenta_contable_id(db, CODIGO_DEPOSITOS_VISTA)
    movs = [
        MovimientoContable(cuenta_contable_id=gasto_id, cuenta_cliente_id=None,
                            tipo_movimiento="D", importe=interes, moneda=cuenta.moneda),
        MovimientoContable(cuenta_contable_id=depositos_id, cuenta_cliente_id=cuenta.cuenta_id,
                            tipo_movimiento="H", importe=interes, moneda=cuenta.moneda),
    ]
    # V7: sin transaccion de cliente -- mismo caso ya contemplado por el libro mayor (ajustes,
    # devengo de intereses, comisiones del sistema). fecha_contable=fecha (no "hoy" del server):
    # necesario para que la simulacion historica de scripts/sembrar_datos_prueba.py distribuya
    # el devengo en el dia simulado, no todos en el dia real en que corre el script.
    registrar_asiento(db, "interes_pasivo", transaccion_id=None, movimientos=movs, fecha_contable=fecha)
