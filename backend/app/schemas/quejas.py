from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class QuejaIn(BaseModel):
    texto: str = Field(min_length=10, max_length=2000)


class QuejaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    queja_id: int
    texto: str
    categoria_sugerida: str | None
    categoria_final: str | None
    estado_revision: str
    creado_en: datetime
