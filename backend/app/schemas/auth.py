from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.tarjetas import TarjetaOut

REGIONES = (
    "Amazonas", "Áncash", "Apurímac", "Arequipa", "Ayacucho", "Cajamarca", "Callao", "Cusco",
    "Huancavelica", "Huánuco", "Ica", "Junín", "La Libertad", "Lambayeque", "Lima", "Loreto",
    "Madre de Dios", "Moquegua", "Pasco", "Piura", "Puno", "San Martín", "Tacna", "Tumbes", "Ucayali",
)


class RegistroIn(BaseModel):
    """RF-01: datos que el cliente ingresa en el onboarding. Lo demas lo asigna el banco."""

    tipo_documento: Literal["DNI", "CE", "PASAPORTE"]
    numero_documento: str = Field(min_length=6, max_length=20)
    nombres: str = Field(min_length=2, max_length=100)
    apellidos: str = Field(min_length=2, max_length=100)
    fecha_nacimiento: date
    email: str = Field(max_length=150, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    telefono: str | None = Field(default=None, max_length=20, pattern=r"^\+?[\d\s]{6,20}$")
    region: Literal[REGIONES]  # type: ignore[valid-type]
    password: str = Field(min_length=8, max_length=72)

    @field_validator("nombres", "apellidos")
    @classmethod
    def _limpiar(cls, v: str) -> str:
        return " ".join(v.split()).title()

    @field_validator("email")
    @classmethod
    def _email_minusculas(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("fecha_nacimiento")
    @classmethod
    def _mayor_de_edad(cls, v: date) -> date:
        hoy = date.today()
        edad = hoy.year - v.year - ((hoy.month, hoy.day) < (v.month, v.day))
        if edad < 18:
            raise ValueError("Debes ser mayor de 18 años")
        if edad > 120:
            raise ValueError("Fecha de nacimiento inválida")
        return v

    @model_validator(mode="after")
    def _documento_segun_tipo(self):
        doc = self.numero_documento.strip().upper()
        if self.tipo_documento == "DNI" and not (doc.isdigit() and len(doc) == 8):
            raise ValueError("El DNI debe tener 8 dígitos")
        if self.tipo_documento == "CE" and not (doc.isalnum() and 9 <= len(doc) <= 12):
            raise ValueError("El carné de extranjería debe tener entre 9 y 12 caracteres")
        self.numero_documento = doc
        return self


class LoginIn(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RegistroOut(TokenOut):
    cliente_id: int
    codigo_cliente: str
    cuenta_id: int
    numero_cuenta: str
    segmento: str
    tarjeta: TarjetaOut
