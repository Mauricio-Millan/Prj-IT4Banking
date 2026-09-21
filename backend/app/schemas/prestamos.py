from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.core.pii import enmascarar_documento
from app.schemas.comunes import Dinero


class SolicitudPrestamoIn(BaseModel):
    monto_original: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    plazo: int = Field(ge=1, le=60)
    # cuenta propia (PEN, activa) donde se acredita el desembolso si se aprueba
    cuenta_id: int


class CuotaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cuota_id: int
    numero: int
    fecha_vencimiento: date
    capital: Dinero
    interes: Dinero
    total: Dinero
    saldo_capital_despues: Dinero
    estado: str
    fecha_pago: date | None
    transaccion_id: int | None


class ProximaCuotaOut(BaseModel):
    numero: int
    fecha_vencimiento: date
    total: Dinero
    estado: str


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
    cuenta_desembolso_numero: str | None = None
    cuotas_total: int = 0
    cuotas_pagadas: int = 0
    proxima_cuota: ProximaCuotaOut | None = None


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


class PagoPrestamoIn(BaseModel):
    cuenta_origen_id: int


class MontoConceptoOut(BaseModel):
    monto: Dinero
    concepto: str


class PagoOut(BaseModel):
    cuota: CuotaOut
    transaccion_id: int
    penalidad: MontoConceptoOut | None
    total_debitado: Dinero
    saldo_capital: Dinero
    estado_prestamo: str
