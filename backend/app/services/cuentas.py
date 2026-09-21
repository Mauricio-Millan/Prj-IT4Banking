from datetime import date, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import RecursoNoEncontrado
from app.models import Cuenta, Transaccion


def listar(db: Session, cliente_id: int) -> list[Cuenta]:
    return list(db.scalars(
        select(Cuenta).where(Cuenta.cliente_id == cliente_id).order_by(Cuenta.fecha_apertura)
    ))


def obtener_propia(db: Session, cliente_id: int, cuenta_id: int) -> Cuenta:
    """404 tanto si la cuenta no existe como si es de otro cliente — misma respuesta (RNF-09)."""
    cuenta = db.scalar(select(Cuenta).where(Cuenta.cuenta_id == cuenta_id, Cuenta.cliente_id == cliente_id))
    if cuenta is None:
        raise RecursoNoEncontrado()
    return cuenta


def movimientos(
    db: Session, cliente_id: int, cuenta_id: int,
    desde: date | None, hasta: date | None, pagina: int, tamano: int,
) -> tuple[list[tuple[Transaccion, str]], int, dict[int, str]]:
    cuenta = obtener_propia(db, cliente_id, cuenta_id)
    filtro = or_(Transaccion.cuenta_origen_id == cuenta.cuenta_id, Transaccion.cuenta_destino_id == cuenta.cuenta_id)
    stmt = select(Transaccion).where(filtro)
    if desde:
        stmt = stmt.where(Transaccion.fecha_hora >= desde)
    if hasta:
        stmt = stmt.where(Transaccion.fecha_hora < hasta + timedelta(days=1))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    filas = db.scalars(
        stmt.order_by(Transaccion.fecha_hora.desc()).offset((pagina - 1) * tamano).limit(tamano)
    ).all()

    # el frontend muestra numero_cuenta, nunca el id interno (HU-Numeracion-Bancaria) — una
    # sola consulta batch para las cuentas involucradas, no N+1 por fila.
    ids_involucrados = {cid for t in filas for cid in (t.cuenta_origen_id, t.cuenta_destino_id) if cid is not None}
    numeros: dict[int, str] = {}
    if ids_involucrados:
        numeros = dict(db.execute(
            select(Cuenta.cuenta_id, Cuenta.numero_cuenta).where(Cuenta.cuenta_id.in_(ids_involucrados))
        ).all())

    return [(t, "salida" if t.cuenta_origen_id == cuenta.cuenta_id else "entrada") for t in filas], total, numeros
