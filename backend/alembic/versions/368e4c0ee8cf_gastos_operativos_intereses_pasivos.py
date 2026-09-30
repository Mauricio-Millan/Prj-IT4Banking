"""gastos operativos intereses pasivos

Revision ID: 368e4c0ee8cf
Revises: 1edc35b39640
Create Date: 2026-09-27 17:30:15.191173

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '368e4c0ee8cf'
down_revision: Union[str, Sequence[str], None] = '1edc35b39640'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CUENTA_CONTABLE = sa.table(
    'cuenta_contable', sa.column('codigo', sa.String), sa.column('nombre', sa.String),
    sa.column('naturaleza', sa.String), sa.column('tipo', sa.String),
)


def upgrade() -> None:
    op.bulk_insert(_CUENTA_CONTABLE, [
        {"codigo": "5101", "nombre": "Gastos por intereses pasivos", "naturaleza": "D", "tipo": "gasto"},
        {"codigo": "5201", "nombre": "Gastos por interconexion de red", "naturaleza": "D", "tipo": "gasto"},
    ])


def downgrade() -> None:
    op.execute("DELETE FROM cuenta_contable WHERE codigo IN ('5101','5201')")
