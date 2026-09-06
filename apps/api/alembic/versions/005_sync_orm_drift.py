"""rename reserved metadata columns and add transactions.updated_at

Brings the migration chain back in line with src/models/__init__.py.

Two drifts had accumulated, both invisible to the test suite because
tests/conftest.py and tests/fixtures_db.py build the schema with
`Base.metadata.create_all` rather than running these migrations:

1. `metadata` is reserved by SQLAlchemy's Declarative API, so the ORM
   attributes were renamed to `case_metadata` / `wallet_metadata` /
   `transaction_metadata`. The columns were never renamed to match, so every
   ORM read/write of those attributes hit a non-existent column on any
   migration-provisioned database.
2. `transactions.updated_at` was omitted from 001_initial (every other table
   got one), while the `Transaction` model has always declared it.

Revision ID: 005
Revises: 004
Create Date: 2026-09-06 00:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None

#: (table, old column name, new column name)
_RENAMES = [
    ("cases", "metadata", "case_metadata"),
    ("wallets", "metadata", "wallet_metadata"),
    ("transactions", "metadata", "transaction_metadata"),
]


def upgrade() -> None:
    for table, old, new in _RENAMES:
        op.alter_column(table, old, new_column_name=new)

    op.add_column(
        "transactions",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("transactions", "updated_at")

    for table, old, new in _RENAMES:
        op.alter_column(table, new, new_column_name=old)
