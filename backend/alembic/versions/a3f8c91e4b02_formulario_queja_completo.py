"""formulario de queja completo (tipo legal, pedido, monto, fecha, referencia)

Revision ID: a3f8c91e4b02
Revises: dd7ba6fc8d41
Create Date: 2026-10-02 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f8c91e4b02'
down_revision: Union[str, Sequence[str], None] = 'dd7ba6fc8d41'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _dropear_default_constraint(bind, tabla: str, columna: str) -> None:
    """server_default crea una DEFAULT CONSTRAINT con nombre auto-generado; DROP COLUMN falla
    mientras exista. Mismo patron que en 50630f92f496_segmentacion_de_clientes.py."""
    nombre = bind.execute(sa.text("""
        SELECT dc.name FROM sys.default_constraints dc
        JOIN sys.tables t ON t.object_id = dc.parent_object_id
        JOIN sys.columns c ON c.object_id = t.object_id AND c.column_id = dc.parent_column_id
        WHERE t.name = :tabla AND c.name = :columna
    """), {"tabla": tabla, "columna": columna}).scalar()
    if nombre:
        bind.execute(sa.text(f"ALTER TABLE {tabla} DROP CONSTRAINT {nombre}"))


def upgrade() -> None:
    op.add_column('queja', sa.Column('tipo_legal', sa.String(10), nullable=False, server_default='reclamo'))
    op.add_column('queja', sa.Column('pedido_consumidor', sa.String(500), nullable=True))
    op.add_column('queja', sa.Column('monto_reclamado', sa.Numeric(18, 2), nullable=True))
    op.add_column('queja', sa.Column('fecha_incidente', sa.Date(), nullable=True))
    op.add_column('queja', sa.Column('cuenta_id', sa.Integer(), nullable=True))
    op.add_column('queja', sa.Column('tarjeta_id', sa.Integer(), nullable=True))
    op.add_column('queja', sa.Column('prestamo_id', sa.Integer(), nullable=True))
    op.add_column('queja', sa.Column('transaccion_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_queja_cuenta', 'queja', 'cuenta', ['cuenta_id'], ['cuenta_id'])
    op.create_foreign_key('fk_queja_tarjeta', 'queja', 'tarjeta', ['tarjeta_id'], ['tarjeta_id'])
    op.create_foreign_key('fk_queja_prestamo', 'queja', 'prestamo', ['prestamo_id'], ['prestamo_id'])
    op.create_foreign_key('fk_queja_transaccion', 'queja', 'transaccion', ['transaccion_id'], ['transaccion_id'])
    op.create_check_constraint('ck_queja_tipo_legal', 'queja', "tipo_legal IN ('reclamo','queja')")


def downgrade() -> None:
    op.drop_constraint('ck_queja_tipo_legal', 'queja', type_='check')
    op.drop_constraint('fk_queja_transaccion', 'queja', type_='foreignkey')
    op.drop_constraint('fk_queja_prestamo', 'queja', type_='foreignkey')
    op.drop_constraint('fk_queja_tarjeta', 'queja', type_='foreignkey')
    op.drop_constraint('fk_queja_cuenta', 'queja', type_='foreignkey')
    op.drop_column('queja', 'transaccion_id')
    op.drop_column('queja', 'prestamo_id')
    op.drop_column('queja', 'tarjeta_id')
    op.drop_column('queja', 'cuenta_id')
    op.drop_column('queja', 'fecha_incidente')
    op.drop_column('queja', 'monto_reclamado')
    op.drop_column('queja', 'pedido_consumidor')
    _dropear_default_constraint(op.get_bind(), 'queja', 'tipo_legal')
    op.drop_column('queja', 'tipo_legal')
