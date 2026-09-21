from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.core.config import settings
from app.core.ruc import ruc_valido
from app.schemas.auth import REGIONES
from app.schemas.tarjetas import TarjetaOut


class ClienteEmpresaIn(BaseModel):
    """POST /backoffice/clientes-empresa, admin-only. RegistroIn (autoservicio) no cambia y
    sigue sin aceptar RUC: el unico camino a una empresa es este endpoint."""

    ruc: str
    razon_social: str = Field(min_length=3, max_length=150)
    representante_nombres: str = Field(min_length=2, max_length=100)
    representante_apellidos: str = Field(min_length=2, max_length=100)
    email: str = Field(max_length=150, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    telefono: str | None = Field(default=None, max_length=20, pattern=r"^\+?[\d\s]{6,20}$")
    region: Literal[REGIONES]  # type: ignore[valid-type]

    @field_validator("ruc")
    @classmethod
    def _validar_ruc(cls, v: str) -> str:
        if not ruc_valido(v):
            raise ValueError("RUC inválido: debe tener 11 dígitos, empezar en 20 y tener un dígito verificador correcto")
        return v

    @field_validator("representante_nombres", "representante_apellidos")
    @classmethod
    def _limpiar(cls, v: str) -> str:
        return " ".join(v.split()).title()

    @field_validator("email")
    @classmethod
    def _email_minusculas_no_corporativo(cls, v: str) -> str:
        v = v.strip().lower()
        if v.endswith(f"@{settings.dominio_corporativo}"):
            raise ValueError("El correo del representante no puede ser un correo corporativo del banco")
        return v


class ClienteEmpresaOut(BaseModel):
    cliente_id: int
    codigo_cliente: str
    ruc: str
    razon_social: str
    cuenta_id: int
    numero_cuenta: str
    cci: str
    # Se devuelve una sola vez, en esta respuesta: el admin la comunica fuera de banda.
    password_temporal: str
    tarjeta: TarjetaOut


class EmpresaListadaOut(BaseModel):
    cliente_id: int
    codigo_cliente: str
    ruc: str
    razon_social: str
    region: str
    fecha_alta: date
    estado: str
