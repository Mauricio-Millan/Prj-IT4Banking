from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Cliente(Base):
    __tablename__ = "cliente"
    __table_args__ = (
        CheckConstraint("tipo_documento IN ('DNI','CE','PASAPORTE')", name="ck_cliente_tipo_documento"),
        CheckConstraint("segmento IN ('joven','clasico','premium','empresa')", name="ck_cliente_segmento"),
        CheckConstraint("estado IN ('activo','bloqueado','cerrado')", name="ck_cliente_estado"),
        # un pasaporte "12345678" y un DNI "12345678" son personas distintas: el UNIQUE es
        # sobre el par, no solo sobre numero_documento (HU-Numeracion-Bancaria).
        UniqueConstraint("tipo_documento", "numero_documento", name="uq_cliente_tipo_numero_documento"),
    )

    cliente_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Identificador de cara al cliente (10 digitos + DV Luhn, ver app/core/numeracion.py).
    # cliente_id (el IDENTITY) nunca se expone: es adivinable y revela el volumen de clientes.
    codigo_cliente: Mapped[str] = mapped_column(String(10), unique=True)
    tipo_documento: Mapped[str] = mapped_column(String(10))
    numero_documento: Mapped[str] = mapped_column(String(20))
    nombres: Mapped[str] = mapped_column(String(100))
    apellidos: Mapped[str] = mapped_column(String(100))
    fecha_nacimiento: Mapped[date] = mapped_column(Date)
    email: Mapped[str] = mapped_column(String(150), unique=True)
    telefono: Mapped[str | None] = mapped_column(String(20))
    region: Mapped[str] = mapped_column(String(50))
    segmento: Mapped[str] = mapped_column(String(20), default="clasico")
    fecha_alta: Mapped[date] = mapped_column(Date, server_default=func.current_date())
    estado: Mapped[str] = mapped_column(String(20), default="activo")
    # HU-Gestion-Usuarios-Internos-Backoffice V13: un caso de un cliente que ademas es
    # empleado del banco solo lo resuelve un admin (conflicto de interes).
    es_empleado: Mapped[bool] = mapped_column(Boolean, default=False)

    usuario: Mapped["Usuario"] = relationship(back_populates="cliente", uselist=False)
    cuentas: Mapped[list["Cuenta"]] = relationship(back_populates="cliente")  # noqa: F821
    prestamos: Mapped[list["Prestamo"]] = relationship(back_populates="cliente")  # noqa: F821


class Usuario(Base):
    __tablename__ = "usuario"
    __table_args__ = (
        CheckConstraint("rol IN ('cliente','analista','admin')", name="ck_usuario_rol"),
        # V1: una identidad es cliente o empleado, nunca ambas. Un empleado que ademas es
        # cliente del banco tiene dos filas en usuario (una por rol), no una fusionada.
        CheckConstraint(
            "(rol = 'cliente' AND cliente_id IS NOT NULL) OR (rol IN ('analista','admin') AND cliente_id IS NULL)",
            name="ck_usuario_rol_cliente",
        ),
        # UNIQUE filtrado, no un unique=True liso: a diferencia de SQLite/Postgres, SQL Server
        # trata multiples NULL como duplicados en un indice UNIQUE comun, lo que impediria
        # tener mas de un usuario interno (cliente_id siempre NULL para analista/admin).
        Index("uq_usuario_cliente_id", "cliente_id", unique=True, mssql_where=text("cliente_id IS NOT NULL")),
    )

    usuario_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cliente_id: Mapped[int | None] = mapped_column(ForeignKey("cliente.cliente_id"))
    email: Mapped[str] = mapped_column(String(150), unique=True)
    password_hash: Mapped[str] = mapped_column(String(100))
    rol: Mapped[str] = mapped_column(String(20), default="cliente")
    ultimo_acceso: Mapped[datetime | None] = mapped_column(DateTime)
    # Ciclo de vida de personal interno (V6-V10): un cliente nunca se desactiva por aqui
    # (ver Cliente.estado); estas dos columnas son solo relevantes para rol analista/admin.
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    debe_cambiar_password: Mapped[bool] = mapped_column(Boolean, default=False)

    cliente: Mapped[Cliente | None] = relationship(back_populates="usuario")
