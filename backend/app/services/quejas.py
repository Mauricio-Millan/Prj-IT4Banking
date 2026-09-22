import json
from datetime import date, datetime, time, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import RecursoNoEncontrado
from app.genai import clasificador
from app.models import Cliente, GenaiLog, Queja
from app.schemas.quejas import QuejaIn, QuejaRevisionOut


class CuotaExcedida(Exception):
    pass


class QuejaYaResuelta(Exception):
    pass


def _quejas_creadas_hoy(db: Session, cliente_id: int) -> int:
    hoy_inicio = datetime.combine(date.today(), time.min)
    hoy_fin = hoy_inicio + timedelta(days=1)
    return db.scalar(
        select(func.count()).select_from(Queja).where(
            Queja.cliente_id == cliente_id, Queja.creado_en >= hoy_inicio, Queja.creado_en < hoy_fin,
        )
    )


def crear(db: Session, cliente_id: int, datos: QuejaIn) -> Queja:
    """RF-09: registro siempre; clasificacion GenAI best-effort en un commit aparte (V4/R8) —
    un fallo del LLM nunca impide ni revierte el registro de la queja."""
    if _quejas_creadas_hoy(db, cliente_id) >= settings.quejas_cuota_diaria:
        raise CuotaExcedida()

    queja = Queja(cliente_id=cliente_id, texto=datos.texto)
    db.add(queja)
    db.commit()
    db.refresh(queja)

    clasificador.clasificar(db, queja)
    db.refresh(queja)
    return queja


def listar(db: Session, cliente_id: int) -> list[Queja]:
    return list(db.scalars(select(Queja).where(Queja.cliente_id == cliente_id).order_by(Queja.creado_en.desc())))


def _motivo_de(db: Session, queja_id: int) -> str | None:
    """'motivo' no es columna de Queja: se reconstruye del genai_log mas reciente de la queja.
    ponytail: una consulta por fila (N+1); la cola de quejas pendientes es chica, optimizar con
    un join si algun dia deja de serlo."""
    log = db.scalar(
        select(GenaiLog).where(GenaiLog.caso_uso == "clasificar_queja", GenaiLog.entidad_id == queja_id)
        .order_by(GenaiLog.genai_log_id.desc()).limit(1)
    )
    if log is None:
        return None
    try:
        return json.loads(log.respuesta_cruda).get("motivo")
    except Exception:
        return None


def listar_cola(db: Session, categoria: str | None = None) -> list[QuejaRevisionOut]:
    stmt = (
        select(Queja, Cliente)
        .join(Cliente, Queja.cliente_id == Cliente.cliente_id)
        .where(Queja.estado_revision == "pendiente")
    )
    if categoria is not None:
        stmt = stmt.where(Queja.categoria_sugerida == categoria)
    stmt = stmt.order_by(case((Queja.prioridad == "alta", 0), else_=1), Queja.creado_en.asc())

    return [
        QuejaRevisionOut(
            queja_id=queja.queja_id, cliente_id=cliente.cliente_id, codigo_cliente=cliente.codigo_cliente,
            cliente_documento=cliente.numero_documento, cliente_nombre=f"{cliente.nombres} {cliente.apellidos}",
            texto=queja.texto, categoria_sugerida=queja.categoria_sugerida, confianza=queja.confianza,
            motivo=_motivo_de(db, queja.queja_id), prioridad=queja.prioridad, estado_revision=queja.estado_revision,
            creado_en=queja.creado_en,
        )
        for queja, cliente in db.execute(stmt).all()
    ]


def revisar(db: Session, queja_id: int, usuario_id: int, categoria_final: str) -> Queja:
    queja = db.get(Queja, queja_id)
    if queja is None:
        raise RecursoNoEncontrado()
    if queja.estado_revision != "pendiente":
        raise QuejaYaResuelta()

    if queja.categoria_sugerida == categoria_final:
        queja.estado_revision = "confirmada"
        decision_humana = "confirmada"
    else:
        queja.estado_revision = "corregida"
        decision_humana = f"corregida: {queja.categoria_sugerida or 'sin_sugerencia'}->{categoria_final}"
    queja.categoria_final = categoria_final
    queja.revisado_por = usuario_id

    ultimo_log = db.scalar(
        select(GenaiLog).where(GenaiLog.caso_uso == "clasificar_queja", GenaiLog.entidad_id == queja_id)
        .order_by(GenaiLog.genai_log_id.desc()).limit(1)
    )
    if ultimo_log is not None:
        ultimo_log.decision_humana = decision_humana

    db.commit()
    db.refresh(queja)
    return queja


def metricas(db: Session) -> dict:
    total = db.scalar(select(func.count()).select_from(Queja).where(Queja.estado_revision != "pendiente"))
    confirmadas = db.scalar(select(func.count()).select_from(Queja).where(Queja.estado_revision == "confirmada"))
    corregidas = db.scalar(select(func.count()).select_from(Queja).where(Queja.estado_revision == "corregida"))
    porcentaje = round(confirmadas / total * 100, 1) if total else 0.0
    return {"total_revisadas": total, "confirmadas": confirmadas, "corregidas": corregidas, "porcentaje_acuerdo": porcentaje}
