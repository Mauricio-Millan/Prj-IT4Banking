"""queja tiempo hasta revision

Revision ID: dd7ba6fc8d41
Revises: 368e4c0ee8cf
Create Date: 2026-09-29 21:35:44.502665

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dd7ba6fc8d41'
down_revision: Union[str, Sequence[str], None] = '368e4c0ee8cf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('queja', sa.Column('revisado_en', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('queja', 'revisado_en')
