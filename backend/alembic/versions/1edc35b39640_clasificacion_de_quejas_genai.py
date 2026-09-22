"""clasificacion de quejas genai

Revision ID: 1edc35b39640
Revises: 50630f92f496
Create Date: 2026-09-22 11:33:02.112697

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1edc35b39640'
down_revision: Union[str, Sequence[str], None] = '50630f92f496'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CATS_VIEJAS = "'tarjeta','prestamo','cuenta','canal_digital','atencion','otro'"
_CATS_NUEVAS = "'producto','servicio','fraude','otro'"


def _dropear_default_constraint(bind, tabla: str, columna: str) -> None:
    nombre = bind.execute(sa.text("""
        SELECT dc.name FROM sys.default_constraints dc
        JOIN sys.tables t ON t.object_id = dc.parent_object_id
        JOIN sys.columns c ON c.object_id = t.object_id AND c.column_id = dc.parent_column_id
        WHERE t.name = :tabla AND c.name = :columna
    """), {"tabla": tabla, "columna": columna}).scalar()
    if nombre:
        bind.execute(sa.text(f"ALTER TABLE {tabla} DROP CONSTRAINT {nombre}"))


def upgrade() -> None:
    # Tabla queja vacia al momento de esta migracion (nunca hubo un flujo que asignara
    # categoria_sugerida/categoria_final hasta esta HU) -> recrear el CHECK es seguro.
    op.add_column('queja', sa.Column('prioridad', sa.String(length=10), nullable=False, server_default='normal'))
    op.create_check_constraint('ck_queja_prioridad', 'queja', "prioridad IN ('normal','alta')")

    op.drop_constraint('ck_queja_cat_sugerida', 'queja', type_='check')
    op.create_check_constraint(
        'ck_queja_cat_sugerida', 'queja', f"categoria_sugerida IS NULL OR categoria_sugerida IN ({_CATS_NUEVAS})",
    )
    op.drop_constraint('ck_queja_cat_final', 'queja', type_='check')
    op.create_check_constraint(
        'ck_queja_cat_final', 'queja', f"categoria_final IS NULL OR categoria_final IN ({_CATS_NUEVAS})",
    )


def downgrade() -> None:
    op.drop_constraint('ck_queja_cat_final', 'queja', type_='check')
    op.create_check_constraint(
        'ck_queja_cat_final', 'queja', f"categoria_final IS NULL OR categoria_final IN ({_CATS_VIEJAS})",
    )
    op.drop_constraint('ck_queja_cat_sugerida', 'queja', type_='check')
    op.create_check_constraint(
        'ck_queja_cat_sugerida', 'queja', f"categoria_sugerida IS NULL OR categoria_sugerida IN ({_CATS_VIEJAS})",
    )

    op.drop_constraint('ck_queja_prioridad', 'queja', type_='check')
    bind = op.get_bind()
    _dropear_default_constraint(bind, 'queja', 'prioridad')
    op.drop_column('queja', 'prioridad')
