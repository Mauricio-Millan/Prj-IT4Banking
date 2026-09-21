"""tarjeta pan cifrado

Revision ID: f54912699357
Revises: 6c5eaa41ceb2
Create Date: 2026-09-20 17:32:31.872428

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f54912699357'
down_revision: Union[str, Sequence[str], None] = '6c5eaa41ceb2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Sin server_default y sin backfill: asume la tabla vacia (mismo reset de HU-Numeracion-Bancaria).
    op.add_column('tarjeta', sa.Column('pan_cifrado', sa.LargeBinary(length=64), nullable=False))
    op.add_column('tarjeta', sa.Column('pan_hmac', sa.LargeBinary(length=32), nullable=False))
    op.create_unique_constraint('uq_tarjeta_pan_hmac', 'tarjeta', ['pan_hmac'])


def downgrade() -> None:
    op.drop_constraint('uq_tarjeta_pan_hmac', 'tarjeta', type_='unique')
    op.drop_column('tarjeta', 'pan_hmac')
    op.drop_column('tarjeta', 'pan_cifrado')
