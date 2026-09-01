"""add wallets.entity_type column

Revision ID: 004
Revises: 003
Create Date: 2026-09-01 00:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("wallets", sa.Column("entity_type", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("wallets", "entity_type")
