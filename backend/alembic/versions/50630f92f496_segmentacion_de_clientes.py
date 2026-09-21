"""segmentacion de clientes

Revision ID: 50630f92f496
Revises: f9b82737b31e
Create Date: 2026-09-21 12:59:04.234953

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '50630f92f496'
down_revision: Union[str, Sequence[str], None] = 'f9b82737b31e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _nombre_check_existente(bind, tabla: str, nombre: str) -> str | None:
    """Mismo patron que en migraciones anteriores (numeracion bancaria, tarjeta): el nombre
    puede no coincidir si SQL Server lo auto-genero en algun punto; se busca por nombre
    conocido primero (ya viene nombrado desde la migracion inicial) y se usa tal cual si existe."""
    existe = bind.execute(sa.text("""
        SELECT cc.name FROM sys.check_constraints cc
        JOIN sys.tables t ON t.object_id = cc.parent_object_id
        WHERE t.name = :tabla AND cc.name = :nombre
    """), {"tabla": tabla, "nombre": nombre}).scalar()
    return existe


def _dropear_default_constraint(bind, tabla: str, columna: str) -> None:
    """server_default crea una DEFAULT CONSTRAINT con nombre auto-generado; DROP COLUMN falla
    mientras exista. Mismo patron que en 884df8f279fe_gestion_usuarios_internos_backoffice.py."""
    nombre = bind.execute(sa.text("""
        SELECT dc.name FROM sys.default_constraints dc
        JOIN sys.tables t ON t.object_id = dc.parent_object_id
        JOIN sys.columns c ON c.object_id = t.object_id AND c.column_id = dc.parent_column_id
        WHERE t.name = :tabla AND c.name = :columna
    """), {"tabla": tabla, "columna": columna}).scalar()
    if nombre:
        bind.execute(sa.text(f"ALTER TABLE {tabla} DROP CONSTRAINT {nombre}"))


def upgrade() -> None:
    # Seguro sobre datos existentes: los 20+ clientes ya sembrados son todos DNI, razon_social
    # queda NULL para ellos (satisface el CHECK nuevo) y dias_bajo_umbral_premium arranca en 0.
    op.add_column('cliente', sa.Column('razon_social', sa.String(length=150), nullable=True))
    op.add_column('cliente', sa.Column(
        'dias_bajo_umbral_premium', sa.Integer(), nullable=False, server_default=sa.text('0'),
    ))

    bind = op.get_bind()
    nombre_check_tipo = _nombre_check_existente(bind, 'cliente', 'ck_cliente_tipo_documento')
    if nombre_check_tipo:
        op.execute(f"ALTER TABLE cliente DROP CONSTRAINT {nombre_check_tipo}")
    op.create_check_constraint(
        'ck_cliente_tipo_documento', 'cliente', "tipo_documento IN ('DNI','CE','PASAPORTE','RUC')",
    )
    op.create_check_constraint(
        'ck_cliente_razon_social', 'cliente',
        "(tipo_documento = 'RUC' AND razon_social IS NOT NULL) OR (tipo_documento <> 'RUC' AND razon_social IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint('ck_cliente_razon_social', 'cliente', type_='check')

    bind = op.get_bind()
    nombre_check_tipo = _nombre_check_existente(bind, 'cliente', 'ck_cliente_tipo_documento')
    if nombre_check_tipo:
        op.execute(f"ALTER TABLE cliente DROP CONSTRAINT {nombre_check_tipo}")
    op.create_check_constraint(
        'ck_cliente_tipo_documento', 'cliente', "tipo_documento IN ('DNI','CE','PASAPORTE')",
    )

    bind_default = op.get_bind()
    _dropear_default_constraint(bind_default, 'cliente', 'dias_bajo_umbral_premium')
    op.drop_column('cliente', 'dias_bajo_umbral_premium')
    op.drop_column('cliente', 'razon_social')
