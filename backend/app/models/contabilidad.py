from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class CuentaContable(Base):
    """Plan de cuentas minimo (caja, depositos a la vista, ingresos por comision).
    Ver Docs/Proyecto/Arquitectura-Core-Banking-Tecnica.md §2.1."""

    __tablename__ = "cuenta_contable"
    __table_args__ = (
        CheckConstraint("naturaleza IN ('D','H')", name="ck_cuenta_contable_naturaleza"),
        CheckConstraint("tipo IN ('activo','pasivo','patrimonio','ingreso','gasto')", name="ck_cuenta_contable_tipo"),
    )

    cuenta_contable_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True)
    nombre: Mapped[str] = mapped_column(String(120))
    naturaleza: Mapped[str] = mapped_column(String(1))  # D: deudora | H: acreedora
    tipo: Mapped[str] = mapped_column(String(20))


class AsientoContable(Base):
    """Un evento economico = un asiento con N movimientos que suman cero (partida doble).
    FK hacia transaccion (no al reves): una transaccion puede tener varios asientos (original +
    reversion) y existen asientos sin transaccion de cliente (ajustes, comisiones del sistema)."""

    __tablename__ = "asiento_contable"
    __table_args__ = (
        CheckConstraint("estado IN ('contabilizado','reversado')", name="ck_asiento_estado"),
        # El indice unico FILTRADO (a lo sumo un asiento original por transaccion; una reversion
        # si puede repetir transaccion_id) no se declara aqui: autogenerate no soporta indices
        # filtrados, se agrega a mano en la migracion como ux_asiento_transaccion_original.
    )

    asiento_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    fecha_contable: Mapped[date] = mapped_column(Date, server_default=func.current_date())
    tipo_operacion: Mapped[str] = mapped_column(String(30))  # 'deposito' | 'retiro' | 'transferencia' | 'reversion'
    transaccion_id: Mapped[int | None] = mapped_column(ForeignKey("transaccion.transaccion_id"), nullable=True)
    estado: Mapped[str] = mapped_column(String(20), default="contabilizado")
    asiento_reversa_id: Mapped[int | None] = mapped_column(ForeignKey("asiento_contable.asiento_id"), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    transaccion: Mapped["Transaccion"] = relationship(back_populates="asientos")  # noqa: F821
    movimientos: Mapped[list["MovimientoContable"]] = relationship(back_populates="asiento")


class MovimientoContable(Base):
    __tablename__ = "movimiento_contable"
    __table_args__ = (
        CheckConstraint("tipo_movimiento IN ('D','H')", name="ck_movimiento_tipo"),
        CheckConstraint("importe > 0", name="ck_movimiento_importe_positivo"),
        CheckConstraint("moneda IN ('PEN','USD')", name="ck_movimiento_moneda"),
        Index("ix_movimiento_asiento", "asiento_id"),
        Index("ix_movimiento_cuenta_cliente", "cuenta_cliente_id"),
    )

    movimiento_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    asiento_id: Mapped[int] = mapped_column(ForeignKey("asiento_contable.asiento_id"))
    cuenta_contable_id: Mapped[int] = mapped_column(ForeignKey("cuenta_contable.cuenta_contable_id"))
    cuenta_cliente_id: Mapped[int | None] = mapped_column(ForeignKey("cuenta.cuenta_id"), nullable=True)
    tipo_movimiento: Mapped[str] = mapped_column(String(1))
    importe: Mapped[Decimal] = mapped_column(Numeric(19, 4))
    moneda: Mapped[str] = mapped_column(String(3))

    asiento: Mapped[AsientoContable] = relationship(back_populates="movimientos")


# Codigos del plan de cuentas minimo (sembrados en la migracion, no son datos de prueba).
CODIGO_CAJA = "1101"
CODIGO_DEPOSITOS_VISTA = "2101"
CODIGO_INGRESOS_COMISION = "4101"
CODIGO_PRESTAMOS_POR_COBRAR = "1301"  # HU-Ciclo-Vida-Prestamo
CODIGO_INGRESOS_INTERESES = "4201"  # HU-Ciclo-Vida-Prestamo


def filas_seed_plan_de_cuentas() -> list[dict]:
    """Fuente unica de las filas semilla: la migracion las inserta con op.bulk_insert,
    los tests con la sesion ORM (ver tests/conftest.py)."""
    return [
        {"codigo": CODIGO_CAJA, "nombre": "Caja", "naturaleza": "D", "tipo": "activo"},
        {"codigo": CODIGO_DEPOSITOS_VISTA, "nombre": "Depositos a la vista", "naturaleza": "H", "tipo": "pasivo"},
        {"codigo": CODIGO_INGRESOS_COMISION, "nombre": "Ingresos por comision", "naturaleza": "H", "tipo": "ingreso"},
        {"codigo": CODIGO_PRESTAMOS_POR_COBRAR, "nombre": "Prestamos por cobrar", "naturaleza": "D", "tipo": "activo"},
        {"codigo": CODIGO_INGRESOS_INTERESES, "nombre": "Ingresos por intereses", "naturaleza": "H", "tipo": "ingreso"},
    ]
