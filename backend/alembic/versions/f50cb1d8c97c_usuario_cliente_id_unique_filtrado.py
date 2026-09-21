"""usuario cliente id unique filtrado

Revision ID: f50cb1d8c97c
Revises: 884df8f279fe
Create Date: 2026-09-20 20:07:32.965829

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f50cb1d8c97c'
down_revision: Union[str, Sequence[str], None] = '884df8f279fe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _nombre_unique_existente(bind, tabla: str, columna: str) -> str | None:
    """Mismo patron que en 6c5eaa41ceb2_numeracion_bancaria.py: el nombre auto-generado
    (UQ__tabla__hash) no es reproducible entre bases, hay que buscarlo por columna."""
    return bind.execute(sa.text("""
        SELECT kc.name
        FROM sys.key_constraints kc
        JOIN sys.tables t ON t.object_id = kc.parent_object_id
        JOIN sys.index_columns ic ON ic.object_id = t.object_id AND ic.index_id = kc.unique_index_id
        JOIN sys.columns c ON c.object_id = t.object_id AND c.column_id = ic.column_id
        WHERE t.name = :tabla AND kc.type = 'UQ' AND c.name = :columna
    """), {"tabla": tabla, "columna": columna}).scalar()


def upgrade() -> None:
    # BUG real encontrado al crear un segundo usuario interno en Azure SQL: a diferencia de
    # SQLite/Postgres, SQL Server trata multiples NULL como duplicados en un indice UNIQUE
    # comun. El UNIQUE liso original (unique=True desde el modelo inicial) le impedia a mas
    # de un usuario interno (cliente_id siempre NULL) coexistir. Se reemplaza por un indice
    # UNIQUE filtrado (WHERE cliente_id IS NOT NULL), que en SQLite es simplemente un UNIQUE
    # normal (SQLite ya trata cada NULL como distinto).
    bind = op.get_bind()
    nombre_viejo = _nombre_unique_existente(bind, 'usuario', 'cliente_id')
    if nombre_viejo:
        op.execute(f"ALTER TABLE usuario DROP CONSTRAINT {nombre_viejo}")
    op.execute(
        "CREATE UNIQUE INDEX uq_usuario_cliente_id ON usuario (cliente_id) WHERE cliente_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX uq_usuario_cliente_id ON usuario")
    op.create_unique_constraint('uq_usuario_cliente_id_legacy', 'usuario', ['cliente_id'])
