from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class TarjetaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tarjeta_id: int
    cuenta_id: int
    tipo_tarjeta: str
    ultimos_4: str
    fecha_emision: date
    fecha_vencimiento: date
    estado: str


class RevelarIn(BaseModel):
    password: str = Field(min_length=1)


class TarjetaRevelada(BaseModel):
    """CVV dinamico: cambia en cada revelado, no se almacena en ninguna tabla (PCI-DSS 3.3.1)."""

    pan: str
    vencimiento: str  # "MM/AA"
    cvv: str
    titular: str
