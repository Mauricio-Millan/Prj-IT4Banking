from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import settings


class UsuarioInternoIn(BaseModel):
    email: str
    rol: Literal["analista", "admin"]
    password_temporal: str = Field(min_length=12, max_length=72)

    @field_validator("email")
    @classmethod
    def _dominio_corporativo(cls, v: str) -> str:
        v = v.strip().lower()
        if not v.endswith(f"@{settings.dominio_corporativo}"):
            raise ValueError(f"El correo debe ser del dominio corporativo @{settings.dominio_corporativo}")
        return v


class UsuarioInternoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    usuario_id: int
    email: str
    rol: str
    activo: bool
    debe_cambiar_password: bool
    ultimo_acceso: datetime | None


class ActualizarUsuarioInternoIn(BaseModel):
    activo: bool | None = None
    rol: Literal["analista", "admin"] | None = None
    password_temporal: str | None = Field(default=None, min_length=12, max_length=72)


class EsEmpleadoIn(BaseModel):
    es_empleado: bool
