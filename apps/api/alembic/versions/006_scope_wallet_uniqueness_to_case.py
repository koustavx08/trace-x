"""scope the wallets unique index to the owning case

`ix_wallets_address_chain` was UNIQUE on (address, chain) globally. Wallets
belong to a case (`wallets.case_id` is a non-null FK), and unrelated
investigations routinely reference the same address -- exchange deposit
wallets, mixers, bridges and token contracts recur across cases by nature. The
global constraint meant the second case to reference any such address failed
on insert with a UniqueViolationError.

src/services/wallet_analysis.py already encodes the intended rule: it rejects
duplicates with "Wallet already tracked in this case", scoped to
(case_id, address, chain). That guard passed for a different case and then the
INSERT blew up against the global index. This migration makes the index match
the guard.

Revision ID: 006
Revises: 005
Create Date: 2026-09-06 00:00:00.000000

"""

from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None

_INDEX = "ix_wallets_address_chain"


def upgrade() -> None:
    op.drop_index(_INDEX, table_name="wallets")
    op.create_index(_INDEX, "wallets", ["case_id", "address", "chain"], unique=True)


def downgrade() -> None:
    # Note: this can fail if the data now contains the same (address, chain)
    # under two different cases -- exactly what the wider constraint forbids.
    op.drop_index(_INDEX, table_name="wallets")
    op.create_index(_INDEX, "wallets", ["address", "chain"], unique=True)
