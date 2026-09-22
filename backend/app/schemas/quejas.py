from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.core.pii import enmascarar_documento


class QuejaIn(BaseModel):
    texto: str = Field(min_length=10, max_length=2000)


class QuejaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    queja_id: int
    texto: str
    categoria_sugerida: str | None
    categoria_final: str | None
    estado_revision: str
    creado_en: datetime


class QuejaRevisionOut(BaseModel):
    """Vista de backoffice: agrega identidad del cliente (enmascarada, HU-Enmascaramiento-PII-Backoffice)
    y 'motivo', que no es columna de Queja (vive en el genai_log mas reciente, ver services/quejas.py)."""

    queja_id: int
    cliente_id: int
    codigo_cliente: str
    cliente_documento: str
    cliente_nombre: str
    texto: str
    categoria_sugerida: str | None
    confianza: Decimal | None
    motivo: str | None
    prioridad: Literal["normal", "alta"]
    estado_revision: str
    creado_en: datetime

    @field_serializer("cliente_documento")
    def _enmascarar_documento(self, v: str) -> str:
        return enmascarar_documento(v)


class DecisionQuejaIn(BaseModel):
    categoria_final: Literal["producto", "servicio", "fraude", "otro"]


class MetricasQuejasOut(BaseModel):
    total_revisadas: int
    confirmadas: int
    corregidas: int
    porcentaje_acuerdo: float
