from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from app.core.pii import enmascarar_documento
from app.schemas.comunes import Dinero


class QuejaIn(BaseModel):
    texto: str = Field(min_length=10, max_length=2000)
    # Extension 2026-10-02: formulario al nivel del Libro de Reclamaciones (D.S. N° 011-2011-PCM).
    tipo_legal: Literal["reclamo", "queja"] = "reclamo"
    pedido_consumidor: str | None = Field(default=None, max_length=500)
    monto_reclamado: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=2)
    fecha_incidente: date | None = None
    # A lo sumo una referencia a la vez -- ver _validaciones.
    cuenta_id: int | None = None
    tarjeta_id: int | None = None
    prestamo_id: int | None = None
    transaccion_id: int | None = None

    @model_validator(mode="after")
    def _validaciones(self):
        referencias = [self.cuenta_id, self.tarjeta_id, self.prestamo_id, self.transaccion_id]
        if sum(r is not None for r in referencias) > 1:
            raise ValueError("Solo se puede referenciar una operación o producto a la vez")
        if self.fecha_incidente and self.fecha_incidente > date.today():
            raise ValueError("La fecha del incidente no puede ser futura")
        return self


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
    categoria_final: str | None
    confianza: Decimal | None
    motivo: str | None
    resumen: str | None
    prioridad: Literal["normal", "alta"]
    estado_revision: str
    revisado_por_email: str | None
    creado_en: datetime
    revisado_en: datetime | None
    modelo_ia: str | None
    senal_vulnerabilidad: bool | None
    senal_amenaza_escalamiento: bool | None
    tipo_legal: Literal["reclamo", "queja"]
    pedido_consumidor: str | None
    monto_reclamado: Dinero | None
    fecha_incidente: date | None
    referencia: str | None

    @field_serializer("cliente_documento")
    def _enmascarar_documento(self, v: str) -> str:
        return enmascarar_documento(v)


class DecisionQuejaIn(BaseModel):
    categoria_final: Literal["producto", "servicio", "fraude", "otro"]


class MetricasQuejasOut(BaseModel):
    total_pendientes: int
    prioridad_alta_pendientes: int
    total_revisadas: int
    confirmadas: int
    corregidas: int
    porcentaje_acuerdo: float
    confianza_promedio: float | None
    tiempo_promedio_revision_horas: float | None
