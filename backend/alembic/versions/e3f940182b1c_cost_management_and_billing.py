"""cost_management_and_billing

Revision ID: e3f940182b1c
Revises: d2e71839a1a2
Create Date: 2026-11-08 00:30:00.000000

"""
from typing import Sequence, Union
import uuid
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e3f940182b1c'
down_revision: Union[str, Sequence[str], None] = 'd2e71839a1a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add monetary cost columns to research_jobs
    op.add_column('research_jobs', sa.Column('cost_usd', sa.Numeric(12, 6), nullable=True))
    op.add_column('research_jobs', sa.Column('budget_reserved_usd', sa.Numeric(12, 6), nullable=True))

    # 2. Create provider_pricing table
    op.create_table(
        'provider_pricing',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('model_name', sa.String(length=100), nullable=True),
        sa.Column('operation_type', sa.String(length=50), nullable=False),
        sa.Column('unit_type', sa.String(length=50), server_default='per_1m_tokens', nullable=False),
        sa.Column('input_rate_usd', sa.Numeric(12, 6), server_default='0.000000', nullable=False),
        sa.Column('output_rate_usd', sa.Numeric(12, 6), server_default='0.000000', nullable=False),
        sa.Column('fixed_request_rate_usd', sa.Numeric(12, 6), server_default='0.000000', nullable=False),
        sa.Column('effective_from', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('effective_to', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('version', sa.Integer(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_provider_pricing_provider', 'provider_pricing', ['provider'], unique=False)
    op.create_index('ix_provider_pricing_operation_type', 'provider_pricing', ['operation_type'], unique=False)
    op.create_index('ix_provider_pricing_is_active', 'provider_pricing', ['is_active'], unique=False)

    # 3. Add cost columns to provider_usage_events
    op.add_column('provider_usage_events', sa.Column('cost_usd', sa.Numeric(12, 6), server_default='0.000000', nullable=False))
    op.add_column('provider_usage_events', sa.Column('pricing_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        'fk_provider_usage_events_pricing_id',
        'provider_usage_events', 'provider_pricing',
        ['pricing_id'], ['id'],
        ondelete='SET NULL'
    )

    # 4. Create user_wallets table
    op.create_table(
        'user_wallets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('balance_usd', sa.Numeric(12, 4), server_default='1.0000', nullable=False),
        sa.Column('reserved_usd', sa.Numeric(12, 4), server_default='0.0000', nullable=False),
        sa.Column('lifetime_spent_usd', sa.Numeric(12, 4), server_default='0.0000', nullable=False),
        sa.Column('monthly_budget_usd', sa.Numeric(12, 4), nullable=True),
        sa.Column('auto_recharge', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('stripe_customer_id', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_user_wallets_user_id', 'user_wallets', ['user_id'], unique=True)

    # 5. Create cost_ledger_entries table
    op.create_table(
        'cost_ledger_entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('research_jobs.id', ondelete='SET NULL'), nullable=True),
        sa.Column('entry_type', sa.String(length=50), nullable=False),
        sa.Column('amount_usd', sa.Numeric(12, 6), nullable=False),
        sa.Column('balance_before_usd', sa.Numeric(12, 4), nullable=False),
        sa.Column('balance_after_usd', sa.Numeric(12, 4), nullable=False),
        sa.Column('reserved_before_usd', sa.Numeric(12, 4), nullable=False),
        sa.Column('reserved_after_usd', sa.Numeric(12, 4), nullable=False),
        sa.Column('idempotency_key', sa.String(length=255), nullable=True),
        sa.Column('description', sa.String(length=255), nullable=False),
        sa.Column('meta_info', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_cost_ledger_entries_user_id', 'cost_ledger_entries', ['user_id'], unique=False)
    op.create_index('ix_cost_ledger_entries_job_id', 'cost_ledger_entries', ['job_id'], unique=False)
    op.create_index('ix_cost_ledger_entries_entry_type', 'cost_ledger_entries', ['entry_type'], unique=False)
    op.create_index('ix_cost_ledger_entries_idempotency_key', 'cost_ledger_entries', ['idempotency_key'], unique=True)
    op.create_index('ix_cost_ledger_entries_created_at', 'cost_ledger_entries', ['created_at'], unique=False)

    # 6. Seed Baseline Provisional Pricing
    conn = op.get_bind()
    pricing_data = [
        {
            "id": uuid.uuid4(),
            "provider": "gemini",
            "model_name": "gemini-2.5-flash",
            "operation_type": "llm_generation",
            "unit_type": "per_1m_tokens",
            "input_rate_usd": 0.075000,
            "output_rate_usd": 0.300000,
            "fixed_request_rate_usd": 0.000000,
            "is_active": True,
            "version": 1,
        },
        {
            "id": uuid.uuid4(),
            "provider": "gemini",
            "model_name": "text-embedding-004",
            "operation_type": "embedding",
            "unit_type": "per_1m_tokens",
            "input_rate_usd": 0.020000,
            "output_rate_usd": 0.000000,
            "fixed_request_rate_usd": 0.000000,
            "is_active": True,
            "version": 1,
        },
        {
            "id": uuid.uuid4(),
            "provider": "tavily",
            "model_name": "tavily-search",
            "operation_type": "web_search",
            "unit_type": "per_request",
            "input_rate_usd": 0.000000,
            "output_rate_usd": 0.000000,
            "fixed_request_rate_usd": 0.005000,
            "is_active": True,
            "version": 1,
        },
    ]
    for p in pricing_data:
        conn.execute(
            sa.text(
                "INSERT INTO provider_pricing (id, provider, model_name, operation_type, unit_type, "
                "input_rate_usd, output_rate_usd, fixed_request_rate_usd, is_active, version, created_at, updated_at) "
                "VALUES (:id, :provider, :model_name, :operation_type, :unit_type, :input_rate_usd, "
                ":output_rate_usd, :fixed_request_rate_usd, :is_active, :version, NOW(), NOW())"
            ),
            p
        )

    # 7. Safe Migration of Existing Users: Seed User Wallets with $1.00 Complimentary Credit
    users_result = conn.execute(sa.text("SELECT id FROM users")).fetchall()
    for row in users_result:
        uid = row[0]
        wallet_id = uuid.uuid4()
        conn.execute(
            sa.text(
                "INSERT INTO user_wallets (id, user_id, balance_usd, reserved_usd, lifetime_spent_usd, created_at, updated_at) "
                "VALUES (:id, :user_id, 1.0000, 0.0000, 0.0000, NOW(), NOW()) "
                "ON CONFLICT (user_id) DO NOTHING"
            ),
            {"id": wallet_id, "user_id": uid}
        )
        conn.execute(
            sa.text(
                "INSERT INTO cost_ledger_entries (id, user_id, entry_type, amount_usd, balance_before_usd, "
                "balance_after_usd, reserved_before_usd, reserved_after_usd, description, created_at, updated_at) "
                "VALUES (:id, :user_id, 'credit_grant', 1.000000, 0.0000, 1.0000, 0.0000, 0.0000, "
                "'Complimentary beta research starter credit', NOW(), NOW())"
            ),
            {"id": uuid.uuid4(), "user_id": uid}
        )


def downgrade() -> None:
    op.drop_index('ix_cost_ledger_entries_created_at', table_name='cost_ledger_entries')
    op.drop_index('ix_cost_ledger_entries_idempotency_key', table_name='cost_ledger_entries')
    op.drop_index('ix_cost_ledger_entries_entry_type', table_name='cost_ledger_entries')
    op.drop_index('ix_cost_ledger_entries_job_id', table_name='cost_ledger_entries')
    op.drop_index('ix_cost_ledger_entries_user_id', table_name='cost_ledger_entries')
    op.drop_table('cost_ledger_entries')

    op.drop_index('ix_user_wallets_user_id', table_name='user_wallets')
    op.drop_table('user_wallets')

    op.drop_constraint('fk_provider_usage_events_pricing_id', 'provider_usage_events', type_='foreignkey')
    op.drop_column('provider_usage_events', 'pricing_id')
    op.drop_column('provider_usage_events', 'cost_usd')

    op.drop_index('ix_provider_pricing_is_active', table_name='provider_pricing')
    op.drop_index('ix_provider_pricing_operation_type', table_name='provider_pricing')
    op.drop_index('ix_provider_pricing_provider', table_name='provider_pricing')
    op.drop_table('provider_pricing')

    op.drop_column('research_jobs', 'budget_reserved_usd')
    op.drop_column('research_jobs', 'cost_usd')

