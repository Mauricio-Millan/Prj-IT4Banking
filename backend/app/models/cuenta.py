import calendar
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, LargeBinary, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Cuenta(Base):
    __tablename__ = "cuenta"
    __table_args__ = (
        CheckConstraint("tipo_cuenta IN ('ahorro','corriente')", name="ck_cuenta_tipo"),
        CheckConstraint("moneda IN ('PEN','USD')", name="ck_cuenta_moneda"),
        CheckConstraint("saldo >= 0", name="ck_cuenta_saldo_no_negativo"),
        CheckConstraint("estado IN ('activa','bloqueada','cerrada')", name="ck_cuenta_estado"),
    )

    cuenta_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("cliente.cliente_id"), index=True)
    # Numeros de cara al cliente (ver app/core/numeracion.py). cuenta_id (el IDENTITY) sigue
    # usandose en las URLs propias (/cuentas/{id}/...), protegidas por RNF-09; lo que el
    # cliente escribe para transferir es numero_cuenta o cci, nunca el id interno.
    numero_cuenta: Mapped[str] = mapped_column(String(14), unique=True)
    cci: Mapped[str] = mapped_column(String(20), unique=True)
    tipo_cuenta: Mapped[str] = mapped_column(String(20), default="ahorro")
    moneda: Mapped[str] = mapped_column(String(3), default="PEN")
    saldo: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    fecha_apertura: Mapped[date] = mapped_column(Date, server_default=func.current_date())
    estado: Mapped[str] = mapped_column(String(20), default="activa")

    cliente: Mapped["Cliente"] = relationship(back_populates="cuentas")  # noqa: F821
    tarjetas: Mapped[list["Tarjeta"]] = relationship(back_populates="cuenta")


class Tarjeta(Base):
    __tablename__ = "tarjeta"
    __table_args__ = (
        CheckConstraint("tipo_tarjeta IN ('debito','credito')", name="ck_tarjeta_tipo"),
        CheckConstraint("estado IN ('activa','bloqueada','vencida')", name="ck_tarjeta_estado"),
    )

    tarjeta_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cuenta_id: Mapped[int] = mapped_column(ForeignKey("cuenta.cuenta_id"), index=True)
    tipo_tarjeta: Mapped[str] = mapped_column(String(10))
    # PCI-DSS: el CVV nunca se almacena (ni cifrado); se genera al vuelo en cada revelado
    # (ver services/tarjetas.py::revelar). El PAN si se custodia cifrado, nunca en claro:
    # ver app/core/tarjetas_crypto.py. ultimos_4 sale del PAN generado, en claro (PCI lo permite).
    ultimos_4: Mapped[str] = mapped_column(String(4))
    pan_cifrado: Mapped[bytes] = mapped_column(LargeBinary(64))
    pan_hmac: Mapped[bytes] = mapped_column(LargeBinary(32), unique=True)
    fecha_emision: Mapped[date] = mapped_column(Date)
    fecha_vencimiento: Mapped[date] = mapped_column(Date)
    estado: Mapped[str] = mapped_column(String(20), default="activa")

    cuenta: Mapped[Cuenta] = relationship(back_populates="tarjetas")


def fecha_vencimiento_tarjeta(fecha_emision: date) -> date:
    """Las tarjetas vencen a fin de mes, 4 anios despues (evita el caso 29 de febrero)."""
    anio = fecha_emision.year + 4
    ultimo_dia = calendar.monthrange(anio, fecha_emision.month)[1]
    return date(anio, fecha_emision.month, ultimo_dia)


class Transaccion(Base):
    __tablename__ = "transaccion"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ('deposito','retiro','transferencia','pago_prestamo','comision','desembolso')",
            name="ck_transaccion_tipo",
        ),
        CheckConstraint("monto > 0", name="ck_transaccion_monto_positivo"),
        CheckConstraint("canal IN ('web','app','cajero','agente','sistema')", name="ck_transaccion_canal"),
        CheckConstraint("estado IN ('aplicada','rechazada','reversada')", name="ck_transaccion_estado"),
        # el pipeline nocturno lee por fecha (marca de agua)
        Index("ix_transaccion_fecha_hora", "fecha_hora"),
    )

    transaccion_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cuenta_origen_id: Mapped[int | None] = mapped_column(ForeignKey("cuenta.cuenta_id"), index=True)
    cuenta_destino_id: Mapped[int | None] = mapped_column(ForeignKey("cuenta.cuenta_id"), index=True)
    fecha_hora: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    tipo: Mapped[str] = mapped_column(String(20))
    monto: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    canal: Mapped[str] = mapped_column(String(10))
    estado: Mapped[str] = mapped_column(String(20), default="aplicada")
    # HU-Tarifario-Comisiones: para que los movimientos se expliquen solos ("Pago cuota 3/12",
    # "Comisión: retiro en red aliada (4.º del mes)") y para ligar una comision a su operacion.
    concepto: Mapped[str | None] = mapped_column(String(80))
    transaccion_origen_id: Mapped[int | None] = mapped_column(ForeignKey("transaccion.transaccion_id"))

    # Python puro, sin columna nueva en transaccion: una transaccion puede sustentar varios
    # asientos (original + reversion). Ver AsientoContable en models/contabilidad.py.
    asientos: Mapped[list["AsientoContable"]] = relationship(back_populates="transaccion")  # noqa: F821
