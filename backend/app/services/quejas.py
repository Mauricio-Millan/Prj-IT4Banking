import json
from datetime import date, datetime, time, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, aliased

from app.core.config import settings
from app.core.exceptions import RecursoNoEncontrado
from app.genai import clasificador
from app.models import Cliente, GenaiLog, Queja, Usuario
from app.schemas.quejas import QuejaIn, QuejaRevisionOut


class CuotaExcedida(Exception):
    pass


class QuejaYaResuelta(Exception):
    pass


class EstadoInvalido(Exception):
    pass


# Extension 2026-09-29 (tablero Kanban): estados reales de Queja.estado_revision + "todos".
ESTADOS_QUEJA = ("pendiente", "confirmada", "corregida")


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


def _resumen_de(db: Session, queja_id: int) -> str | None:
    """Extension 2026-09-28: mismo patron que _motivo_de, pero para el campo "resumen" del
    prompt v2 (2-3 oraciones en vez de una frase de 20 palabras). Quejas clasificadas con el
    prompt v1 (anteriores a esta extension) no tienen "resumen" en su respuesta_cruda -> None,
    nunca rompe la cola (R5/V del resto de la HU)."""
    log = db.scalar(
        select(GenaiLog).where(GenaiLog.caso_uso == "clasificar_queja", GenaiLog.entidad_id == queja_id)
        .order_by(GenaiLog.genai_log_id.desc()).limit(1)
    )
    if log is None:
        return None
    try:
        return json.loads(log.respuesta_cruda).get("resumen")
    except Exception:
        return None


def listar_cola(db: Session, estado: str = "pendiente", categoria: str | None = None) -> list[QuejaRevisionOut]:
    """estado="todos": sin filtro (tablero Kanban, pide las tres columnas de una vez). Cualquier
    otro valor fuera de ESTADOS_QUEJA -> EstadoInvalido (422), mismo patron que
    HU-Backoffice-Cartera-Prestamos::listar_cartera. Default "pendiente": el comportamiento de
    hoy no cambia para quien no pase el parametro."""
    if estado != "todos" and estado not in ESTADOS_QUEJA:
        raise EstadoInvalido()

    Revisor = aliased(Usuario)
    stmt = (
        select(Queja, Cliente, Revisor.email)
        .join(Cliente, Queja.cliente_id == Cliente.cliente_id)
        .outerjoin(Revisor, Queja.revisado_por == Revisor.usuario_id)
    )
    if estado != "todos":
        stmt = stmt.where(Queja.estado_revision == estado)
    if categoria is not None:
        stmt = stmt.where(Queja.categoria_sugerida == categoria)
    stmt = stmt.order_by(case((Queja.prioridad == "alta", 0), else_=1), Queja.creado_en.asc())

    return [
        QuejaRevisionOut(
            queja_id=queja.queja_id, cliente_id=cliente.cliente_id, codigo_cliente=cliente.codigo_cliente,
            cliente_documento=cliente.numero_documento, cliente_nombre=f"{cliente.nombres} {cliente.apellidos}",
            texto=queja.texto, categoria_sugerida=queja.categoria_sugerida, categoria_final=queja.categoria_final,
            confianza=queja.confianza, motivo=_motivo_de(db, queja.queja_id), resumen=_resumen_de(db, queja.queja_id),
            prioridad=queja.prioridad, estado_revision=queja.estado_revision, revisado_por_email=revisor_email,
            creado_en=queja.creado_en,
        )
        for queja, cliente, revisor_email in db.execute(stmt).all()
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
    queja.revisado_en = datetime.utcnow()

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

    # Extension 2026-09-27 (AHT proxy): promedio calculado en Python, no con DATEDIFF de SQL
    # Server -- evita depender de una funcion que SQLite (usado en los tests) no tiene igual.
    # La cola de quejas es chica; nunca justifica optimizar esto a un solo round-trip SQL.
    tiempos = db.execute(
        select(Queja.creado_en, Queja.revisado_en).where(Queja.estado_revision != "pendiente", Queja.revisado_en.is_not(None))
    ).all()
    tiempo_promedio_revision_horas = (
        round(sum((revisado - creado).total_seconds() for creado, revisado in tiempos) / len(tiempos) / 3600, 2)
        if tiempos else None
    )

    return {
        "total_revisadas": total, "confirmadas": confirmadas, "corregidas": corregidas,
        "porcentaje_acuerdo": porcentaje, "tiempo_promedio_revision_horas": tiempo_promedio_revision_horas,
    }
