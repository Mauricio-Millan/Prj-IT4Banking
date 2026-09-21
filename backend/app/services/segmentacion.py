"""HU-Segmentacion-Clientes: re-evaluacion diaria de joven/clasico/premium (nunca empresa),
invocada por app/jobs/cierre_diario.py despues de recalcular mora."""
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AuditLog, Cliente, Cuenta

UMBRAL_SALDO_PREMIUM = Decimal("20000.00")  # PEN, suma de saldos de cuentas activas del cliente
DIAS_BAJO_UMBRAL_PARA_DEGRADAR = 30  # histeresis: evita subir y bajar por un movimiento puntual


def _segmento_por_edad(fecha_nacimiento: date, hoy: date | None = None) -> str:
    hoy = hoy or date.today()
    edad = hoy.year - fecha_nacimiento.year - ((hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day))
    return "joven" if edad < 30 else "clasico"


def calcular_nuevo_segmento(
    segmento_actual: str, dias_bajo_umbral: int, saldo_total: Decimal, fecha_nacimiento: date, hoy: date | None = None,
) -> tuple[str, int]:
    """Pura, sin DB: el llamador ya filtro 'empresa' antes de invocar esto (V8). Devuelve
    (nuevo_segmento, nuevos_dias_bajo_umbral_premium)."""
    if saldo_total >= UMBRAL_SALDO_PREMIUM:
        return "premium", 0

    if segmento_actual == "premium":
        dias = dias_bajo_umbral + 1
        if dias >= DIAS_BAJO_UMBRAL_PARA_DEGRADAR:
            return _segmento_por_edad(fecha_nacimiento, hoy), 0
        return "premium", dias  # sigue premium mientras no se cumplan los 30 dias

    return _segmento_por_edad(fecha_nacimiento, hoy), 0  # joven/clasico, nunca retrocede clasico->joven


def _suma_saldos_cuentas_activas_pen(db: Session, cliente_id: int) -> Decimal:
    return db.scalar(
        select(func.coalesce(func.sum(Cuenta.saldo), 0)).where(
            Cuenta.cliente_id == cliente_id, Cuenta.estado == "activa", Cuenta.moneda == "PEN",
        )
    )


def reevaluar_segmento(db: Session, cliente: Cliente, hoy: date | None = None) -> None:
    if cliente.segmento == "empresa":
        return  # V8: nunca se toca automaticamente

    saldo_total = _suma_saldos_cuentas_activas_pen(db, cliente.cliente_id)
    anterior = cliente.segmento
    nuevo, dias = calcular_nuevo_segmento(cliente.segmento, cliente.dias_bajo_umbral_premium, saldo_total,
                                           cliente.fecha_nacimiento, hoy)
    cliente.dias_bajo_umbral_premium = dias
    if nuevo != anterior:
        cliente.segmento = nuevo
        # V12: todo cambio de segmento deja rastro. Mismo patron que el resto del audit_log
        # (entidad_id = PK de la fila afectada); el motivo anterior->nuevo no cabe en el
        # esquema actual de audit_log (sin columna de detalle libre), igual que ningun otro
        # cambio de estado en esta app lo registra hoy.
        db.add(AuditLog(usuario_id=None, accion="cambio_segmento", entidad="cliente", entidad_id=str(cliente.cliente_id)))
