"""numeracion bancaria

Revision ID: 6c5eaa41ceb2
Revises: b0328a02a241
Create Date: 2026-09-20 14:35:16.898298

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '6c5eaa41ceb2'
down_revision: Union[str, Sequence[str], None] = 'b0328a02a241'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _nombre_unique_existente(bind, tabla: str, columna: str) -> str | None:
    """El UNIQUE original de `cliente.numero_documento` (base migration) no tenia nombre
    explicito: SQL Server le asigno uno aleatorio (UQ__cliente__<hash>), distinto en cada
    base nueva. Buscarlo por columna en vez de hardcodear el nombre hace esta migracion
    reproducible en cualquier instalacion, no solo en la nuestra."""
    return bind.execute(sa.text("""
        SELECT kc.name
        FROM sys.key_constraints kc
        JOIN sys.tables t ON t.object_id = kc.parent_object_id
        JOIN sys.index_columns ic ON ic.object_id = t.object_id AND ic.index_id = kc.unique_index_id
        JOIN sys.columns c ON c.object_id = t.object_id AND c.column_id = ic.column_id
        WHERE t.name = :tabla AND kc.type = 'UQ' AND c.name = :columna
    """), {"tabla": tabla, "columna": columna}).scalar()


def upgrade() -> None:
    bind = op.get_bind()

    op.add_column('cliente', sa.Column('codigo_cliente', sa.String(length=10), nullable=False))
    op.create_unique_constraint('uq_cliente_codigo_cliente', 'cliente', ['codigo_cliente'])

    # un pasaporte "12345678" y un DNI "12345678" son personas distintas: UNIQUE sobre el par,
    # no solo sobre numero_documento.
    nombre_viejo = _nombre_unique_existente(bind, 'cliente', 'numero_documento')
    if nombre_viejo:
        op.execute(f"ALTER TABLE cliente DROP CONSTRAINT {nombre_viejo}")
    op.create_unique_constraint('uq_cliente_tipo_numero_documento', 'cliente', ['tipo_documento', 'numero_documento'])

    op.add_column('cuenta', sa.Column('numero_cuenta', sa.String(length=14), nullable=False))
    op.create_unique_constraint('uq_cuenta_numero_cuenta', 'cuenta', ['numero_cuenta'])
    op.add_column('cuenta', sa.Column('cci', sa.String(length=20), nullable=False))
    op.create_unique_constraint('uq_cuenta_cci', 'cuenta', ['cci'])


def downgrade() -> None:
    op.drop_constraint('uq_cuenta_cci', 'cuenta', type_='unique')
    op.drop_column('cuenta', 'cci')
    op.drop_constraint('uq_cuenta_numero_cuenta', 'cuenta', type_='unique')
    op.drop_column('cuenta', 'numero_cuenta')

    op.drop_constraint('uq_cliente_tipo_numero_documento', 'cliente', type_='unique')
    op.create_unique_constraint('uq_cliente_numero_documento', 'cliente', ['numero_documento'])

    op.drop_constraint('uq_cliente_codigo_cliente', 'cliente', type_='unique')
    op.drop_column('cliente', 'codigo_cliente')
