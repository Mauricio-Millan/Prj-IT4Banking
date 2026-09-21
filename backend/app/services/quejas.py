from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Queja
from app.schemas.quejas import QuejaIn


def crear(db: Session, cliente_id: int, datos: QuejaIn) -> Queja:
    """RF-09: solo registro en esta ronda — sin llamada a GenAI, categoria_sugerida queda null."""
    queja = Queja(cliente_id=cliente_id, texto=datos.texto)
    db.add(queja)
    db.commit()
    db.refresh(queja)
    return queja


def listar(db: Session, cliente_id: int) -> list[Queja]:
    return list(db.scalars(select(Queja).where(Queja.cliente_id == cliente_id).order_by(Queja.creado_en.desc())))
