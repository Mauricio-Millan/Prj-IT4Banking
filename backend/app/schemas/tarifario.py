from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class TarifaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    codigo: str
    nombre: str
    monto: Decimal
    moneda: str
    gratis_por_mes: int | None
    vigente_desde: date


class TarifarioOut(BaseModel):
    tarifas: list[TarifaOut]
    nota_itf: str = "El ITF (impuesto del 0.005% aplicado por ley) no es una comisión del banco y no está incluido en este tarifario."
