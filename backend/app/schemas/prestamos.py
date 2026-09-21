from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_serializer

from app.core.pii import enmascarar_documento
from app.schemas.comunes import Dinero


class SolicitudPrestamoIn(BaseModel):
    monto_original: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    plazo: int = Field(ge=1, le=60)


class PrestamoOut(BaseModel):
    prestamo_id: int
    monto_original: Dinero
    saldo_capital: Dinero
    tasa: Decimal  # porcentaje, no es dinero -> no usa Dinero
    plazo: int
    fecha_desembolso: date | None
    fecha_vencimiento: date | None
    dias_mora: int
    bucket_mora: str
    estado: str


class PrestamoRevisionOut(PrestamoOut):
    """Vista de backoffice: agrega la identidad del cliente para que el analista sepa a quien
    evalua. cliente_documento sale enmascarado (Ley 29733): el analista ya tiene codigo_cliente
    para identificar sin necesitar el DNI completo."""
    cliente_id: int
    cliente_nombre: str
    cliente_documento: str

    @field_serializer("cliente_documento")
    def _enmascarar_documento(self, v: str) -> str:
        return enmascarar_documento(v)


class DecisionPrestamoIn(BaseModel):
    decision: Literal["aprobar", "rechazar"]
