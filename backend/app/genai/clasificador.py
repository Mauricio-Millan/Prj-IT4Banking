"""HU-Clasificacion-Quejas-GenAI. La IA propone (categoria_sugerida, confianza, senales); el
codigo decide con reglas auditables (prioridad, validacion de salida); un humano confirma o
corrige (categoria_final) antes de que la clasificacion cuente para algo. Ver §Riesgos de
alucinacion R1-R9 en la HU: cada mitigacion tiene su reflejo aqui."""
import json
import time
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.genai import masking
from app.genai.client import complete
from app.models import Cuenta, GenaiLog, Prestamo, Queja, Tarjeta, Transaccion
from app.models.genai import CATEGORIAS_QUEJA

# Extension 2026-09-28: v2 reemplaza "motivo" (20 palabras) por "resumen" (2-3 oraciones,
# ~50 palabras) -- v1 queda en Git como historial, no se borra (permite reconstruir/auditar
# respuestas viejas que ya quedaron guardadas en genai_log con prompt_version="v1").
PROMPT_VERSION = "v2"
PROMPT_TEMPLATE = (Path(__file__).parent / "prompts" / "clasificar_queja_v2.txt").read_text(encoding="utf-8")
SYSTEM_PROMPT = "Eres un clasificador de quejas bancarias. Sigue exactamente el formato de salida solicitado."


def calcular_prioridad(categoria: str, senales: dict, reincidente: bool) -> str:
    """V10/V12/V13/V14: fraude, cualquier senal de apoyo, o reincidencia -> alta. Nunca al reves:
    en el peor caso, 'normal'. Ninguna de estas fuentes decide sola salvo fraude (regulatorio)."""
    if categoria == "fraude":
        return "alta"
    if senales.get("vulnerabilidad") or senales.get("amenaza_escalamiento"):
        return "alta"
    if reincidente:
        return "alta"
    return "normal"


def _validar_salida(respuesta_cruda: str) -> tuple[str | None, Decimal | None, dict]:
    """Nunca lanza. Dos fallbacks distintos, a proposito (no el mismo para los dos casos):
    - R5, JSON que ni siquiera se puede parsear: no hay nada que rescatar -> (None, None, {}),
      la queja queda sin categoria_sugerida (null), 100% para triage manual.
    - R1, JSON valido pero con una categoria fuera de CATEGORIAS_QUEJA o una confianza fuera de
      rango: SI hubo una respuesta interpretable, solo que invalida -> se degrada a 'otro' con
      confianza 0 en vez de descartarla por completo."""
    try:
        datos = json.loads(respuesta_cruda)
    except Exception:
        return None, None, {}

    try:
        categoria = datos["categoria"]
        confianza = Decimal(str(datos["confianza"]))
        senales_crudas = datos.get("senales", {})
        senales = {
            "vulnerabilidad": senales_crudas.get("vulnerabilidad") is True,
            "amenaza_escalamiento": senales_crudas.get("amenaza_escalamiento") is True,
        }
        if categoria not in CATEGORIAS_QUEJA or not (0 <= confianza <= 1):
            raise ValueError
        return categoria, confianza, senales
    except Exception:
        return "otro", Decimal("0"), {}


def _es_reincidente(db: Session, cliente_id: int, categoria: str, queja_id_actual: int) -> bool:
    """Hecho objetivo, sin IA (V13): otra queja del mismo cliente, misma categoria_final, en
    los ultimos 30 dias, o cualquier OTRA queja aun pendiente. Excluye la propia queja_id_actual
    (que ya esta insertada y 'pendiente' para cuando esto corre) para no contarse a si misma."""
    hace_30_dias = datetime.utcnow() - timedelta(days=30)
    return db.scalar(
        select(Queja.queja_id).where(
            Queja.cliente_id == cliente_id,
            Queja.queja_id != queja_id_actual,
            or_(
                and_(Queja.categoria_final == categoria, Queja.creado_en >= hace_30_dias),
                Queja.estado_revision == "pendiente",
            ),
        ).limit(1)
    ) is not None


def _contexto_referencia(db: Session, queja: Queja) -> str:
    """Extension 2026-10-02: si la queja referencia una operacion/producto propio, se lo
    describe al modelo en una linea -- nunca mas de lo que ya es visible en otra parte del
    sistema (ultimos_4 de la tarjeta, numero de cuenta, montos). Vacio si no hay referencia."""
    if queja.tarjeta_id is not None:
        t = db.get(Tarjeta, queja.tarjeta_id)
        if t:
            return f"Contexto adicional: el cliente referencia su tarjeta terminada en {t.ultimos_4}.\n\n"
    if queja.cuenta_id is not None:
        c = db.get(Cuenta, queja.cuenta_id)
        if c:
            return f"Contexto adicional: el cliente referencia su cuenta terminada en {c.numero_cuenta[-4:]}.\n\n"
    if queja.prestamo_id is not None:
        p = db.get(Prestamo, queja.prestamo_id)
        if p:
            return f"Contexto adicional: el cliente referencia un préstamo por S/ {p.monto_original:.2f}.\n\n"
    if queja.transaccion_id is not None:
        tr = db.get(Transaccion, queja.transaccion_id)
        if tr:
            return f"Contexto adicional: el cliente referencia una transacción de tipo {tr.tipo} por S/ {tr.monto:.2f}.\n\n"
    return ""


def clasificar(db: Session, queja: Queja) -> None:
    """Best-effort (R8): si falla cualquier paso, la queja queda tal cual (pendiente, sin
    sugerencia). Commit propio, separado del INSERT de la queja: un fallo aqui nunca revierte
    el registro que ya vio el cliente."""
    inicio = time.monotonic()
    texto_enmascarado = ""
    try:
        texto_enmascarado = masking.enmascarar(queja.texto)
        contexto_adicional = _contexto_referencia(db, queja)
        prompt = (PROMPT_TEMPLATE
                  .replace("{texto_enmascarado}", texto_enmascarado)
                  .replace("{contexto_adicional}", contexto_adicional))
        respuesta_cruda, modelo = complete(system=SYSTEM_PROMPT, prompt=prompt)
        categoria, confianza, senales = _validar_salida(respuesta_cruda)
    except Exception:
        categoria, confianza, senales, respuesta_cruda, modelo = None, None, {}, "", "error"
    latencia_ms = int((time.monotonic() - inicio) * 1000)

    if categoria is not None:
        reincidente = _es_reincidente(db, queja.cliente_id, categoria, queja.queja_id)
        queja.categoria_sugerida = categoria
        queja.confianza = confianza
        queja.prioridad = calcular_prioridad(categoria, senales, reincidente)
        db.flush()

    db.add(GenaiLog(
        caso_uso="clasificar_queja", entidad_id=queja.queja_id, prompt_version=PROMPT_VERSION,
        modelo=modelo, prompt_enmascarado=texto_enmascarado if categoria is not None else "",
        respuesta_cruda=respuesta_cruda, latencia_ms=latencia_ms,
    ))
    db.commit()
