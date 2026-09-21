from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Cliente


def listar_con_cuentas(db: Session, pagina: int, tamano: int) -> tuple[list[Cliente], int]:
    total = db.scalar(select(func.count()).select_from(Cliente))
    filas = list(db.scalars(
        select(Cliente)
        .options(selectinload(Cliente.cuentas))
        .order_by(Cliente.cliente_id)
        .offset((pagina - 1) * tamano)
        .limit(tamano)
    ))
    return filas, total
