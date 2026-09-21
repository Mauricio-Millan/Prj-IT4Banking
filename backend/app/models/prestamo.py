import calendar
from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Prestamo(Base):
    __tablename__ = "prestamo"
    __table_args__ = (
        CheckConstraint("monto_original > 0", name="ck_prestamo_monto_positivo"),
        CheckConstraint("saldo_capital >= 0", name="ck_prestamo_saldo_no_negativo"),
        CheckConstraint("tasa >= 0 AND tasa <= 100", name="ck_prestamo_tasa"),
        CheckConstraint("plazo BETWEEN 1 AND 60", name="ck_prestamo_plazo_meses"),
        CheckConstraint("dias_mora >= 0", name="ck_prestamo_dias_mora"),
        CheckConstraint("bucket_mora IN ('0','1-30','31-60','61-90','>90')", name="ck_prestamo_bucket"),
        CheckConstraint("estado IN ('solicitado','aprobado','rechazado','vigente','cancelado')", name="ck_prestamo_estado"),
    )

    prestamo_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("cliente.cliente_id"), index=True)
    # Cuenta propia (PEN, activa) elegida en la solicitud; ahi se acredita el desembolso
    # (HU-Ciclo-Vida-Prestamo). NOT NULL: toda solicitud, aprobada o no, ya la exige.
    cuenta_desembolso_id: Mapped[int] = mapped_column(ForeignKey("cuenta.cuenta_id"))
    monto_original: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    saldo_capital: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    tasa: Mapped[Decimal] = mapped_column(Numeric(5, 2))  # TEA anual en %
    plazo: Mapped[int] = mapped_column(Integer)  # meses
    fecha_desembolso: Mapped[date | None] = mapped_column(Date)
    dias_mora: Mapped[int] = mapped_column(Integer, default=0)
    bucket_mora: Mapped[str] = mapped_column(String(5), default="0")
    estado: Mapped[str] = mapped_column(String(20), default="solicitado")

    cliente: Mapped["Cliente"] = relationship(back_populates="prestamos")  # noqa: F821
    cuenta_desembolso: Mapped["Cuenta"] = relationship()  # noqa: F821
    cuotas: Mapped[list["Cuota"]] = relationship(back_populates="prestamo", order_by="Cuota.numero")


class Cuota(Base):
    """Cronograma de un prestamo (sistema frances, cuota fija): ver generar_cronograma en
    services/prestamos.py. Se genera una sola vez, al desembolsar."""

    __tablename__ = "cuota"
    __table_args__ = (
        UniqueConstraint("prestamo_id", "numero", name="uq_cuota_prestamo_numero"),
        # Comparacion redondeada a centavos, no "total = capital + interes" liso: en SQL
        # Server (DECIMAL exacto) son equivalentes, pero SQLite guarda NUMERIC como float de
        # doble precision y una suma de 3 columnas independientes puede diferir en el ultimo
        # bit — el CHECK liso rechazaba filas correctas en los tests (SQLite-only).
        CheckConstraint(
            "ROUND(total * 100, 0) = ROUND(capital * 100, 0) + ROUND(interes * 100, 0)",
            name="ck_cuota_total",
        ),
        CheckConstraint("estado IN ('pendiente','pagada','vencida')", name="ck_cuota_estado"),
    )

    cuota_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    prestamo_id: Mapped[int] = mapped_column(ForeignKey("prestamo.prestamo_id"), index=True)
    numero: Mapped[int] = mapped_column(Integer)
    fecha_vencimiento: Mapped[date] = mapped_column(Date)
    capital: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    interes: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    total: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    saldo_capital_despues: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    estado: Mapped[str] = mapped_column(String(10), default="pendiente")
    fecha_pago: Mapped[date | None] = mapped_column(Date)
    # la transaccion pago_prestamo que la pago (no la de la penalidad, que es una comision aparte)
    transaccion_id: Mapped[int | None] = mapped_column(ForeignKey("transaccion.transaccion_id"))

    prestamo: Mapped[Prestamo] = relationship(back_populates="cuotas")


def bucket_de(dias_mora: int) -> str:
    if dias_mora <= 0:
        return "0"
    if dias_mora <= 30:
        return "1-30"
    if dias_mora <= 60:
        return "31-60"
    if dias_mora <= 90:
        return "61-90"
    return ">90"


def fecha_vencimiento_de(fecha_desembolso: date, plazo: int) -> date:
    """fecha_desembolso + plazo meses. Sin columna nueva ni dependencia (solo stdlib calendar)."""
    mes_total = fecha_desembolso.month - 1 + plazo
    anio = fecha_desembolso.year + mes_total // 12
    mes = mes_total % 12 + 1
    dia = min(fecha_desembolso.day, calendar.monthrange(anio, mes)[1])
    return date(anio, mes, dia)
