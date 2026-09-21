from datetime import date

from pydantic import BaseModel, ConfigDict

from app.schemas.comunes import Dinero


class CuentaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cuenta_id: int
    numero_cuenta: str
    cci: str
    tipo_cuenta: str
    moneda: str
    saldo: Dinero
    fecha_apertura: date
    estado: str


class SaldoOut(BaseModel):
    cuenta_id: int
    numero_cuenta: str
    moneda: str
    saldo: Dinero


class ComisionRetiroOut(BaseModel):
    monto: Dinero
    # None si la tarifa no tiene cuota gratuita; si la tiene, cuantos retiros gratis quedan este mes.
    retiros_gratis_restantes: int | None
