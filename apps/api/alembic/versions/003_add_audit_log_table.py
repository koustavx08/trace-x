"""add audit_log table

Revision ID: 003
Revises: 002
Create Date: 2026-09-01 00:00:00.000000

"""

import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column(
            "actor_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True, index=True
        ),
        sa.Column("action", sa.String(50), nullable=False, index=True),
        sa.Column("resource_type", sa.String(50), nullable=True),
        sa.Column("resource_id", sa.String(255), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            index=True,
        ),
        sa.Column("ip_address", sa.String(45), nullable=True),
    )

    op.create_index("ix_audit_log_actor_created", "audit_log", ["actor_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_log_actor_created", table_name="audit_log")
    op.drop_table("audit_log")
