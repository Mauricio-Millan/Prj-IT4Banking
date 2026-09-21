from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import RecursoNoEncontrado
from app.models import AuditLog, Cliente, Prestamo
from app.models.prestamo import fecha_vencimiento_de
from app.schemas.prestamos import PrestamoOut, PrestamoRevisionOut, SolicitudPrestamoIn

# ponytail: regla de elegibilidad naive por segmento (limite de autoevaluacion, tasa);
# reemplazar por un modelo de riesgo real en la fase de GenAI/analitica del curso.
LIMITES_SEGMENTO: dict[str, tuple[Decimal, Decimal]] = {
    "joven": (Decimal("5000"), Decimal("22.00")),
    "clasico": (Decimal("15000"), Decimal("18.50")),
    "premium": (Decimal("50000"), Decimal("14.90")),
    "empresa": (Decimal("100000"), Decimal("16.00")),
}


class PrestamoYaResuelto(Exception):
    pass


class RequiereAdmin(Exception):
    """V13: un caso de un cliente marcado es_empleado (conflicto de interes) solo lo resuelve un admin."""


def a_schema(p: Prestamo) -> PrestamoOut:
    return PrestamoOut(
        prestamo_id=p.prestamo_id, monto_original=p.monto_original, saldo_capital=p.saldo_capital, tasa=p.tasa,
        plazo=p.plazo, fecha_desembolso=p.fecha_desembolso,
        fecha_vencimiento=fecha_vencimiento_de(p.fecha_desembolso, p.plazo) if p.fecha_desembolso else None,
        dias_mora=p.dias_mora, bucket_mora=p.bucket_mora, estado=p.estado,
    )


def solicitar(db: Session, cliente_id: int, usuario_id: int, datos: SolicitudPrestamoIn, ip: str | None = None) -> Prestamo:
    """RF-06: hibrido. Monto grande -> revision humana en backoffice (como un banco real).
    Monto dentro del limite del segmento -> decision automatica instantanea."""
    segmento = db.scalar(select(Cliente.segmento).where(Cliente.cliente_id == cliente_id))
    limite, tasa = LIMITES_SEGMENTO[segmento]

    if datos.monto_original > limite:
        estado, fecha_desembolso = "solicitado", None
    else:
        tiene_mora_vigente = db.scalar(
            select(Prestamo.prestamo_id).where(
                Prestamo.cliente_id == cliente_id, Prestamo.estado == "vigente", Prestamo.dias_mora > 0
            )
        ) is not None
        if tiene_mora_vigente:
            estado, fecha_desembolso = "rechazado", None
        else:
            estado, fecha_desembolso = "vigente", date.today()

    prestamo = Prestamo(
        cliente_id=cliente_id, monto_original=datos.monto_original, saldo_capital=datos.monto_original,
        tasa=tasa, plazo=datos.plazo, fecha_desembolso=fecha_desembolso, dias_mora=0, bucket_mora="0", estado=estado,
    )
    db.add(prestamo)
    db.flush()
    db.add(AuditLog(usuario_id=usuario_id, accion="crear", entidad="prestamo", entidad_id=str(prestamo.prestamo_id), ip=ip))
    db.commit()
    db.refresh(prestamo)
    return prestamo


def listar(db: Session, cliente_id: int) -> list[Prestamo]:
    return list(db.scalars(
        select(Prestamo).where(Prestamo.cliente_id == cliente_id).order_by(Prestamo.prestamo_id.desc())
    ))


def listar_pendientes(db: Session) -> list[PrestamoRevisionOut]:
    filas = db.execute(
        select(Prestamo, Cliente)
        .join(Cliente, Prestamo.cliente_id == Cliente.cliente_id)
        .where(Prestamo.estado == "solicitado")
        .order_by(Prestamo.prestamo_id)
    ).all()
    return [
        PrestamoRevisionOut(
            **a_schema(p).model_dump(), cliente_id=c.cliente_id,
            cliente_nombre=f"{c.nombres} {c.apellidos}", cliente_documento=c.numero_documento,
        )
        for p, c in filas
    ]


def resolver(db: Session, prestamo_id: int, decision: str, usuario_id: int, rol: str, ip: str | None = None) -> Prestamo:
    prestamo = db.get(Prestamo, prestamo_id)
    if prestamo is None:
        raise RecursoNoEncontrado()
    if prestamo.estado != "solicitado":
        raise PrestamoYaResuelto()

    cliente = db.get(Cliente, prestamo.cliente_id)
    if cliente.es_empleado and rol != "admin":
        raise RequiereAdmin()

    if decision == "aprobar":
        prestamo.estado = "vigente"
        prestamo.fecha_desembolso = date.today()
    else:
        prestamo.estado = "rechazado"

    db.flush()
    # sin columna revisado_por en Prestamo (a diferencia de Queja) — el audit log ya cubre quien/cuando.
    db.add(AuditLog(usuario_id=usuario_id, accion=f"{decision}_prestamo", entidad="prestamo",
                     entidad_id=str(prestamo_id), ip=ip))
    db.commit()
    db.refresh(prestamo)
    return prestamo
