"""add hashed_password to users

Revision ID: 002
Revises: 001
Create Date: 2024-01-15 00:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("hashed_password", sa.String(255), nullable=False, server_default="")
    )


def downgrade() -> None:
    op.drop_column("users", "hashed_password")
