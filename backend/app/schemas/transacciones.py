from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.config import settings
from app.core.numeracion import digito_verificador
from app.schemas.comunes import Dinero


class TransaccionIn(BaseModel):
    tipo: Literal["deposito", "retiro", "transferencia"]
    monto: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    # la cuenta origen sale del listado propio del cliente (RF-03), nunca se tipea
    cuenta_origen_id: int | None = None
    # numero_cuenta (14 digitos) o cci (20 digitos) de destino: lo que el cliente escribe
    cuenta_destino: str | None = None
    # HU-Tarifario-Comisiones: canal real, no fijo. 'web' no es valido para deposito/retiro
    # (ocurren en cajero o agente, nunca en la app); transferencia siempre es 'web' y no se tipea.
    canal: Literal["cajero", "agente"] | None = None

    @field_validator("cuenta_destino")
    @classmethod
    def _validar_destino(cls, v: str | None) -> str | None:
        if v is None:
            return v
        limpio = v.replace(" ", "").replace("-", "")
        if not limpio.isdigit() or len(limpio) not in (14, 20):
            raise ValueError("Número de cuenta o CCI inválido")
        if len(limpio) == 14:
            if digito_verificador(limpio[:-1]) != limpio[-1]:
                raise ValueError("Número de cuenta inválido (dígito verificador)")
        else:  # 20 -> CCI: banco(3) + oficina(3) + cuenta(12) + DV(2)
            if limpio[:3] != settings.banco_codigo_cce:
                raise ValueError("Solo se admiten transferencias entre cuentas de este banco")
            if digito_verificador(limpio[:6]) != limpio[18]:
                raise ValueError("CCI inválido (dígito verificador de banco/oficina)")
            if digito_verificador(limpio[6:18]) != limpio[19]:
                raise ValueError("CCI inválido (dígito verificador de cuenta)")
        return limpio

    @model_validator(mode="after")
    def _cuentas_segun_tipo(self):
        if self.tipo == "deposito" and self.cuenta_destino is None:
            raise ValueError("cuenta_destino es requerido para un depósito")
        if self.tipo == "retiro" and self.cuenta_origen_id is None:
            raise ValueError("cuenta_origen_id es requerido para un retiro")
        if self.tipo == "transferencia" and (self.cuenta_origen_id is None or self.cuenta_destino is None):
            raise ValueError("una transferencia requiere cuenta_origen_id y cuenta_destino")
        if self.tipo in ("deposito", "retiro") and self.canal is None:
            raise ValueError("canal es requerido para depósito o retiro ('cajero' o 'agente')")
        return self


class ComisionOut(BaseModel):
    monto: Dinero
    concepto: str


class TransaccionOut(BaseModel):
    transaccion_id: int
    fecha_hora: datetime
    tipo: str
    monto: Dinero
    canal: str
    estado: str
    concepto: str | None = None
    cuenta_origen_id: int | None
    cuenta_destino_id: int | None
    cuenta_origen_numero: str | None = None
    cuenta_destino_numero: str | None = None
    comision: ComisionOut | None = None


class MovimientoOut(TransaccionOut):
    direccion: Literal["entrada", "salida"]


class MovimientosPagina(BaseModel):
    items: list[MovimientoOut]
    total: int
    pagina: int
    tamano: int
