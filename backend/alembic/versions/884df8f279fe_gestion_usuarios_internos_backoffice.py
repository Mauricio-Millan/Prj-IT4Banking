"""gestion usuarios internos backoffice

Revision ID: 884df8f279fe
Revises: f54912699357
Create Date: 2026-09-20 19:57:07.164708

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '884df8f279fe'
down_revision: Union[str, Sequence[str], None] = 'f54912699357'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _dropear_default_constraint(bind, tabla: str, columna: str) -> None:
    """server_default crea una DEFAULT CONSTRAINT con nombre auto-generado (DF__tabla__col__hash),
    distinto en cada base; DROP COLUMN falla mientras exista. Mismo patron que
    _nombre_unique_existente en 6c5eaa41ceb2_numeracion_bancaria.py, pero para sys.default_constraints."""
    nombre = bind.execute(sa.text("""
        SELECT dc.name FROM sys.default_constraints dc
        JOIN sys.tables t ON t.object_id = dc.parent_object_id
        JOIN sys.columns c ON c.object_id = t.object_id AND c.column_id = dc.parent_column_id
        WHERE t.name = :tabla AND c.name = :columna
    """), {"tabla": tabla, "columna": columna}).scalar()
    if nombre:
        bind.execute(sa.text(f"ALTER TABLE {tabla} DROP CONSTRAINT {nombre}"))


def upgrade() -> None:
    # server_default (no solo el default de Python en el modelo): esta migracion corre sobre
    # datos existentes (clientes y el analista de demo ya sembrados), a diferencia de las
    # migraciones de Numeracion-Bancaria/Tarjeta que asumian tablas vacias tras el reset.
    op.add_column('cliente', sa.Column('es_empleado', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('usuario', sa.Column('activo', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column('usuario', sa.Column('debe_cambiar_password', sa.Boolean(), nullable=False, server_default=sa.false()))
    # V1: una identidad es cliente o empleado, nunca ambas.
    op.create_check_constraint(
        'ck_usuario_rol_cliente', 'usuario',
        "(rol = 'cliente' AND cliente_id IS NOT NULL) OR (rol IN ('analista','admin') AND cliente_id IS NULL)",
    )


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_constraint('ck_usuario_rol_cliente', 'usuario', type_='check')
    _dropear_default_constraint(bind, 'usuario', 'debe_cambiar_password')
    op.drop_column('usuario', 'debe_cambiar_password')
    _dropear_default_constraint(bind, 'usuario', 'activo')
    op.drop_column('usuario', 'activo')
    _dropear_default_constraint(bind, 'cliente', 'es_empleado')
    op.drop_column('cliente', 'es_empleado')
