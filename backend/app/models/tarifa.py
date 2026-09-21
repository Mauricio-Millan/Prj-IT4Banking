from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Tarifa(Base):
    """Catalogo de comisiones (HU-Tarifario-Comisiones). Publico via GET /tarifario;
    cobrado por app/services/comisiones.py::calcular/cobrar."""

    __tablename__ = "tarifa"
    __table_args__ = (CheckConstraint("monto >= 0", name="ck_tarifa_monto_no_negativo"),)

    tarifa_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True)
    nombre: Mapped[str] = mapped_column(String(120))
    evento: Mapped[str] = mapped_column(String(40))
    monto: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    moneda: Mapped[str] = mapped_column(String(3), default="PEN")
    # None = sin cuota gratuita (ej. la penalidad); N = las primeras N veces del mes no cobran.
    gratis_por_mes: Mapped[int | None] = mapped_column(Integer)
    activa: Mapped[bool] = mapped_column(Boolean, default=True)
    vigente_desde: Mapped[date] = mapped_column(Date)


def filas_seed_tarifario() -> list[dict]:
    """Fuente unica: la migracion las inserta con op.bulk_insert, los tests con la sesion ORM
    (mismo patron que filas_seed_plan_de_cuentas en models/contabilidad.py)."""
    desde = date(2026, 1, 1)
    return [
        {"codigo": "RET-RED", "nombre": "Retiro en cajero o agente de red aliada", "evento": "retiro",
         "monto": Decimal("3.00"), "moneda": "PEN", "gratis_por_mes": 3, "activa": True, "vigente_desde": desde},
        {"codigo": "PRE-ATR", "nombre": "Penalidad por cuota atrasada", "evento": "pago_cuota_vencida",
         "monto": Decimal("15.00"), "moneda": "PEN", "gratis_por_mes": None, "activa": True, "vigente_desde": desde},
        {"codigo": "TRF-INTRA", "nombre": "Transferencia entre cuentas BancoCloud", "evento": "transferencia",
         "monto": Decimal("0.00"), "moneda": "PEN", "gratis_por_mes": None, "activa": True, "vigente_desde": desde},
        {"codigo": "MAN-CTA", "nombre": "Mantenimiento de cuenta PEN/USD", "evento": "mantenimiento",
         "monto": Decimal("0.00"), "moneda": "PEN", "gratis_por_mes": None, "activa": True, "vigente_desde": desde},
        {"codigo": "TAR-EMI", "nombre": "Emisión y revelado de tarjeta virtual", "evento": "tarjeta",
         "monto": Decimal("0.00"), "moneda": "PEN", "gratis_por_mes": None, "activa": True, "vigente_desde": desde},
        {"codigo": "TRF-INTER", "nombre": "Transferencia interbancaria inmediata", "evento": "transferencia_interbancaria",
         "monto": Decimal("3.50"), "moneda": "PEN", "gratis_por_mes": None, "activa": False, "vigente_desde": desde},
    ]
