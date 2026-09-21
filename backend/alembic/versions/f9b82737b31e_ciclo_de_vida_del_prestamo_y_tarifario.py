"""ciclo de vida del prestamo y tarifario

Revision ID: f9b82737b31e
Revises: f50cb1d8c97c
Create Date: 2026-09-21 12:05:39.683070

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f9b82737b31e'
down_revision: Union[str, Sequence[str], None] = 'f50cb1d8c97c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TARIFA = sa.table(
    'tarifa', sa.column('codigo', sa.String), sa.column('nombre', sa.String), sa.column('evento', sa.String),
    sa.column('monto', sa.Numeric), sa.column('moneda', sa.String), sa.column('gratis_por_mes', sa.Integer),
    sa.column('activa', sa.Boolean), sa.column('vigente_desde', sa.Date),
)
_CUENTA_CONTABLE = sa.table(
    'cuenta_contable', sa.column('codigo', sa.String), sa.column('nombre', sa.String),
    sa.column('naturaleza', sa.String), sa.column('tipo', sa.String),
)


def upgrade() -> None:
    op.create_table('tarifa',
        sa.Column('tarifa_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('codigo', sa.String(length=20), nullable=False),
        sa.Column('nombre', sa.String(length=120), nullable=False),
        sa.Column('evento', sa.String(length=40), nullable=False),
        sa.Column('monto', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('moneda', sa.String(length=3), nullable=False),
        sa.Column('gratis_por_mes', sa.Integer(), nullable=True),
        sa.Column('activa', sa.Boolean(), nullable=False),
        sa.Column('vigente_desde', sa.Date(), nullable=False),
        sa.CheckConstraint('monto >= 0', name='ck_tarifa_monto_no_negativo'),
        sa.PrimaryKeyConstraint('tarifa_id'),
        sa.UniqueConstraint('codigo'),
    )
    op.create_table('cuota',
        sa.Column('cuota_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('prestamo_id', sa.Integer(), nullable=False),
        sa.Column('numero', sa.Integer(), nullable=False),
        sa.Column('fecha_vencimiento', sa.Date(), nullable=False),
        sa.Column('capital', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('interes', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('total', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('saldo_capital_despues', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('estado', sa.String(length=10), nullable=False),
        sa.Column('fecha_pago', sa.Date(), nullable=True),
        sa.Column('transaccion_id', sa.Integer(), nullable=True),
        sa.CheckConstraint("estado IN ('pendiente','pagada','vencida')", name='ck_cuota_estado'),
        # Redondeado a centavos: equivalente a "total = capital + interes" en SQL Server
        # (DECIMAL exacto), pero tolerante al float de SQLite en los tests.
        sa.CheckConstraint('ROUND(total * 100, 0) = ROUND(capital * 100, 0) + ROUND(interes * 100, 0)', name='ck_cuota_total'),
        sa.ForeignKeyConstraint(['prestamo_id'], ['prestamo.prestamo_id'], ),
        sa.ForeignKeyConstraint(['transaccion_id'], ['transaccion.transaccion_id'], ),
        sa.PrimaryKeyConstraint('cuota_id'),
        sa.UniqueConstraint('prestamo_id', 'numero', name='uq_cuota_prestamo_numero'),
    )
    op.create_index(op.f('ix_cuota_prestamo_id'), 'cuota', ['prestamo_id'], unique=False)

    # Sin backfill: se limpiaron a mano los 8 prestamos de prueba sembrados antes de esta HU
    # (no tenian cronograma ni desembolso, incompatibles con el nuevo invariante V2). Tabla
    # vacia al momento de esta migracion -> NOT NULL directo, sin paso intermedio nullable.
    op.add_column('prestamo', sa.Column('cuenta_desembolso_id', sa.Integer(), nullable=False))
    op.create_foreign_key('fk_prestamo_cuenta_desembolso', 'prestamo', 'cuenta', ['cuenta_desembolso_id'], ['cuenta_id'])

    op.add_column('transaccion', sa.Column('concepto', sa.String(length=80), nullable=True))
    op.add_column('transaccion', sa.Column('transaccion_origen_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_transaccion_transaccion_origen', 'transaccion', 'transaccion',
                           ['transaccion_origen_id'], ['transaccion_id'])

    bind = op.get_bind()
    nombre_check_tipo = bind.execute(sa.text("""
        SELECT cc.name FROM sys.check_constraints cc
        JOIN sys.tables t ON t.object_id = cc.parent_object_id
        WHERE t.name = 'transaccion' AND cc.name = 'ck_transaccion_tipo'
    """)).scalar()
    if nombre_check_tipo:
        op.execute(f"ALTER TABLE transaccion DROP CONSTRAINT {nombre_check_tipo}")
    op.create_check_constraint(
        'ck_transaccion_tipo', 'transaccion',
        "tipo IN ('deposito','retiro','transferencia','pago_prestamo','comision','desembolso')",
    )

    op.bulk_insert(_CUENTA_CONTABLE, [
        {"codigo": "1301", "nombre": "Prestamos por cobrar", "naturaleza": "D", "tipo": "activo"},
        {"codigo": "4201", "nombre": "Ingresos por intereses", "naturaleza": "H", "tipo": "ingreso"},
    ])
    op.bulk_insert(_TARIFA, [
        {"codigo": "RET-RED", "nombre": "Retiro en cajero o agente de red aliada", "evento": "retiro",
         "monto": 3.00, "moneda": "PEN", "gratis_por_mes": 3, "activa": True, "vigente_desde": "2026-01-01"},
        {"codigo": "PRE-ATR", "nombre": "Penalidad por cuota atrasada", "evento": "pago_cuota_vencida",
         "monto": 15.00, "moneda": "PEN", "gratis_por_mes": None, "activa": True, "vigente_desde": "2026-01-01"},
        {"codigo": "TRF-INTRA", "nombre": "Transferencia entre cuentas BancoCloud", "evento": "transferencia",
         "monto": 0.00, "moneda": "PEN", "gratis_por_mes": None, "activa": True, "vigente_desde": "2026-01-01"},
        {"codigo": "MAN-CTA", "nombre": "Mantenimiento de cuenta PEN/USD", "evento": "mantenimiento",
         "monto": 0.00, "moneda": "PEN", "gratis_por_mes": None, "activa": True, "vigente_desde": "2026-01-01"},
        {"codigo": "TAR-EMI", "nombre": "Emisión y revelado de tarjeta virtual", "evento": "tarjeta",
         "monto": 0.00, "moneda": "PEN", "gratis_por_mes": None, "activa": True, "vigente_desde": "2026-01-01"},
        {"codigo": "TRF-INTER", "nombre": "Transferencia interbancaria inmediata", "evento": "transferencia_interbancaria",
         "monto": 3.50, "moneda": "PEN", "gratis_por_mes": None, "activa": False, "vigente_desde": "2026-01-01"},
    ])


def downgrade() -> None:
    op.execute("DELETE FROM tarifa")
    op.execute("DELETE FROM cuenta_contable WHERE codigo IN ('1301','4201')")

    bind = op.get_bind()
    nombre_check_tipo = bind.execute(sa.text("""
        SELECT cc.name FROM sys.check_constraints cc
        JOIN sys.tables t ON t.object_id = cc.parent_object_id
        WHERE t.name = 'transaccion' AND cc.name = 'ck_transaccion_tipo'
    """)).scalar()
    if nombre_check_tipo:
        op.execute(f"ALTER TABLE transaccion DROP CONSTRAINT {nombre_check_tipo}")
    op.create_check_constraint(
        'ck_transaccion_tipo', 'transaccion',
        "tipo IN ('deposito','retiro','transferencia','pago_prestamo','comision')",
    )

    op.drop_constraint('fk_transaccion_transaccion_origen', 'transaccion', type_='foreignkey')
    op.drop_column('transaccion', 'transaccion_origen_id')
    op.drop_column('transaccion', 'concepto')

    op.drop_constraint('fk_prestamo_cuenta_desembolso', 'prestamo', type_='foreignkey')
    op.drop_column('prestamo', 'cuenta_desembolso_id')

    op.drop_index(op.f('ix_cuota_prestamo_id'), table_name='cuota')
    op.drop_table('cuota')
    op.drop_table('tarifa')
