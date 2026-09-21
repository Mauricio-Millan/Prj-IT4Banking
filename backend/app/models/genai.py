from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

CATEGORIAS_QUEJA = ("tarjeta", "prestamo", "cuenta", "canal_digital", "atencion", "otro")
_CATS_SQL = ",".join(f"'{c}'" for c in CATEGORIAS_QUEJA)


class Queja(Base):
    """RF-09: clasificada por GenAI, siempre revisada por un analista (human-in-the-loop)."""

    __tablename__ = "queja"
    __table_args__ = (
        CheckConstraint(f"categoria_sugerida IS NULL OR categoria_sugerida IN ({_CATS_SQL})", name="ck_queja_cat_sugerida"),
        CheckConstraint(f"categoria_final IS NULL OR categoria_final IN ({_CATS_SQL})", name="ck_queja_cat_final"),
        CheckConstraint("estado_revision IN ('pendiente','confirmada','corregida')", name="ck_queja_estado_revision"),
    )

    queja_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("cliente.cliente_id"), index=True)
    texto: Mapped[str] = mapped_column(Text)
    categoria_sugerida: Mapped[str | None] = mapped_column(String(20))
    confianza: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    categoria_final: Mapped[str | None] = mapped_column(String(20))
    estado_revision: Mapped[str] = mapped_column(String(20), default="pendiente", index=True)
    revisado_por: Mapped[int | None] = mapped_column(ForeignKey("usuario.usuario_id"))
    creado_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ResumenEjecutivo(Base):
    """RF-10: resumen generado desde KPIs agregados; solo lo aprobado se muestra."""

    __tablename__ = "resumen_ejecutivo"
    __table_args__ = (
        CheckConstraint("estado_revision IN ('pendiente','aprobado','rechazado')", name="ck_resumen_estado_revision"),
    )

    resumen_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    periodo: Mapped[str] = mapped_column(String(7))  # YYYY-MM
    kpis_entrada: Mapped[str] = mapped_column(Text)  # JSON con las cifras provistas al modelo
    texto_generado: Mapped[str] = mapped_column(Text)
    texto_final: Mapped[str | None] = mapped_column(Text)
    estado_revision: Mapped[str] = mapped_column(String(20), default="pendiente")
    revisado_por: Mapped[int | None] = mapped_column(ForeignKey("usuario.usuario_id"))
    creado_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class GenaiLog(Base):
    """Trazabilidad de cada llamada al LLM: prompt enmascarado, modelo, salida y decision humana."""

    __tablename__ = "genai_log"

    genai_log_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    caso_uso: Mapped[str] = mapped_column(String(30))  # clasificar_queja | resumen_ejecutivo
    entidad_id: Mapped[int | None] = mapped_column(Integer)
    prompt_version: Mapped[str] = mapped_column(String(20))
    modelo: Mapped[str] = mapped_column(String(60))
    prompt_enmascarado: Mapped[str] = mapped_column(Text)
    respuesta_cruda: Mapped[str] = mapped_column(Text)
    decision_humana: Mapped[str | None] = mapped_column(String(200))
    latencia_ms: Mapped[int | None] = mapped_column(Integer)
    creado_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
