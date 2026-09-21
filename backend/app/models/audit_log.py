from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class AuditLog(Base):
    """RNF-04: toda mutacion deja rastro. Sin FK a usuario para que el log sobreviva a bajas."""

    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_entidad", "entidad", "entidad_id"),)

    audit_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    usuario_id: Mapped[int | None] = mapped_column(Integer)
    accion: Mapped[str] = mapped_column(String(50))  # crear | actualizar | login | login_fallido ...
    entidad: Mapped[str] = mapped_column(String(50))
    entidad_id: Mapped[str | None] = mapped_column(String(50))
    fecha_hora: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    ip: Mapped[str | None] = mapped_column(String(45))
