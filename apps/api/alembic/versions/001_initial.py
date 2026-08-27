"""Initial migration

Revision ID: 001
Revises: 
Create Date: 2024-01-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('email', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('role', sa.Enum('analyst', 'supervisor', 'admin', name='userrole'), default='analyst', nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        'cases',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('case_number', sa.String(50), unique=True, nullable=False, index=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('crime_type', sa.Enum('fraud', 'money_laundering', 'ransomware', 'darknet_market', 'sanctions_evasion', 'other', name='crimetype'), default='fraud', nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', sa.Enum('open', 'in_progress', 'closed', 'archived', name='casestatus'), default='open', nullable=False),
        sa.Column('assigned_to', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True, index=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        'wallets',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('case_id', UUID(as_uuid=True), sa.ForeignKey('cases.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('address', sa.String(66), nullable=False, index=True),
        sa.Column('chain', sa.String(50), nullable=False, index=True),
        sa.Column('label', sa.String(100), nullable=True),
        sa.Column('attribution_status', sa.Enum('unverified', 'under_review', 'attributed', 'confirmed', name='attributionstatus'), default='unverified', nullable=False),
        sa.Column('risk_score', sa.Numeric(5, 2), default=0.0, nullable=False),
        sa.Column('entity_name', sa.String(255), nullable=True),
        sa.Column('entity_confidence', sa.String(20), nullable=True),
        sa.Column('first_seen_tx_hash', sa.String(66), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        'transactions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('wallet_id', UUID(as_uuid=True), sa.ForeignKey('wallets.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('tx_hash', sa.String(66), nullable=False, index=True, unique=True),
        sa.Column('block_number', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column('from_address', sa.String(66), nullable=False, index=True),
        sa.Column('to_address', sa.String(66), nullable=False, index=True),
        sa.Column('value', sa.String(78), nullable=False),
        sa.Column('value_usd', sa.Numeric(18, 2), nullable=True),
        sa.Column('token_address', sa.String(66), nullable=True),
        sa.Column('token_symbol', sa.String(20), nullable=True),
        sa.Column('method', sa.String(100), nullable=True),
        sa.Column('is_suspicious', sa.Boolean(), default=False, nullable=False),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        'investigation_runs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('case_id', UUID(as_uuid=True), sa.ForeignKey('cases.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('wallet_id', UUID(as_uuid=True), sa.ForeignKey('wallets.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('status', sa.Enum('pending', 'running', 'completed', 'failed', name='investigationstatus'), default='pending', nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('config', sa.JSON(), nullable=True),
        sa.Column('result_summary', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        'reports',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('case_id', UUID(as_uuid=True), sa.ForeignKey('cases.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('investigation_run_id', UUID(as_uuid=True), sa.ForeignKey('investigation_runs.id'), nullable=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('findings', sa.JSON(), nullable=False),
        sa.Column('risk_assessment', sa.JSON(), nullable=False),
        sa.Column('graph_snapshot', sa.JSON(), nullable=True),
        sa.Column('generated_by', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('format', sa.String(10), default='json', nullable=False),
        sa.Column('file_path', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_index('ix_cases_status_created', 'cases', ['status', 'created_at'])
    op.create_index('ix_cases_assignee_status', 'cases', ['assigned_to', 'status'])
    op.create_index('ix_wallets_case_chain', 'wallets', ['case_id', 'chain'])
    op.create_index('ix_wallets_address_chain', 'wallets', ['address', 'chain'], unique=True)
    op.create_index('ix_transactions_wallet_timestamp', 'transactions', ['wallet_id', 'timestamp'])
    op.create_index('ix_transactions_from_to', 'transactions', ['from_address', 'to_address'])
    op.create_index('ix_investigation_runs_case_status', 'investigation_runs', ['case_id', 'status'])
    op.create_index('ix_investigation_runs_wallet_status', 'investigation_runs', ['wallet_id', 'status'])
    op.create_index('ix_reports_case_created', 'reports', ['case_id', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_reports_case_created', table_name='reports')
    op.drop_index('ix_investigation_runs_wallet_status', table_name='investigation_runs')
    op.drop_index('ix_investigation_runs_case_status', table_name='investigation_runs')
    op.drop_index('ix_transactions_from_to', table_name='transactions')
    op.drop_index('ix_transactions_wallet_timestamp', table_name='transactions')
    op.drop_index('ix_wallets_address_chain', table_name='wallets')
    op.drop_index('ix_wallets_case_chain', table_name='wallets')
    op.drop_index('ix_cases_assignee_status', table_name='cases')
    op.drop_index('ix_cases_status_created', table_name='cases')

    op.drop_table('reports')
    op.drop_table('investigation_runs')
    op.drop_table('transactions')
    op.drop_table('wallets')
    op.drop_table('cases')
    op.drop_table('users')

    op.execute('DROP TYPE IF EXISTS userrole')
    op.execute('DROP TYPE IF EXISTS crimetype')
    op.execute('DROP TYPE IF EXISTS casestatus')
    op.execute('DROP TYPE IF EXISTS attributionstatus')
    op.execute('DROP TYPE IF EXISTS investigationstatus')