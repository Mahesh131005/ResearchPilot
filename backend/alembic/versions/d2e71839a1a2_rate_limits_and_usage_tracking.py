"""rate_limits_and_usage_tracking

Revision ID: d2e71839a1a2
Revises: c1f82e5a40b9
Create Date: 2026-11-07 22:50:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd2e71839a1a2'
down_revision: Union[str, Sequence[str], None] = 'c1f82e5a40b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add client_token and performance indices to research_jobs
    op.add_column('research_jobs', sa.Column('client_token', sa.String(length=255), nullable=True))
    op.create_index('ix_research_jobs_client_token', 'research_jobs', ['client_token'], unique=False)
    op.create_index('ix_research_jobs_user_status', 'research_jobs', ['user_id', 'status'], unique=False)
    op.create_index('ix_research_jobs_user_created', 'research_jobs', ['user_id', 'created_at'], unique=False)

    # 2. Create user_quotas table for custom per-user quota overrides
    op.create_table(
        'user_quotas',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('hourly_submissions_limit', sa.Integer(), nullable=True),
        sa.Column('daily_jobs_limit', sa.Integer(), nullable=True),
        sa.Column('monthly_jobs_limit', sa.Integer(), nullable=True),
        sa.Column('concurrent_jobs_limit', sa.Integer(), nullable=True),
        sa.Column('tavily_searches_per_job_limit', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_user_quotas_user_id', 'user_quotas', ['user_id'], unique=True)

    # 3. Create provider_usage_events table for idempotent token & search tracking
    op.create_table(
        'provider_usage_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('research_jobs.id', ondelete='SET NULL'), nullable=True),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('operation_type', sa.String(length=50), nullable=False),
        sa.Column('model_name', sa.String(length=100), nullable=True),
        sa.Column('input_tokens', sa.Integer(), server_default='0', nullable=False),
        sa.Column('output_tokens', sa.Integer(), server_default='0', nullable=False),
        sa.Column('total_tokens', sa.Integer(), server_default='0', nullable=False),
        sa.Column('embedding_tokens', sa.Integer(), server_default='0', nullable=False),
        sa.Column('request_count', sa.Integer(), server_default='1', nullable=False),
        sa.Column('search_depth', sa.String(length=50), nullable=True),
        sa.Column('is_estimated', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('usage_metadata_available', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('idempotency_key', sa.String(length=255), nullable=True),
        sa.Column('meta_info', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_provider_usage_events_user_id', 'provider_usage_events', ['user_id'], unique=False)
    op.create_index('ix_provider_usage_events_job_id', 'provider_usage_events', ['job_id'], unique=False)
    op.create_index('ix_provider_usage_events_provider', 'provider_usage_events', ['provider'], unique=False)
    op.create_index('ix_provider_usage_events_operation_type', 'provider_usage_events', ['operation_type'], unique=False)
    op.create_index('ix_provider_usage_events_idempotency_key', 'provider_usage_events', ['idempotency_key'], unique=True)
    op.create_index('ix_provider_usage_events_created_at', 'provider_usage_events', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_provider_usage_events_created_at', table_name='provider_usage_events')
    op.drop_index('ix_provider_usage_events_idempotency_key', table_name='provider_usage_events')
    op.drop_index('ix_provider_usage_events_operation_type', table_name='provider_usage_events')
    op.drop_index('ix_provider_usage_events_provider', table_name='provider_usage_events')
    op.drop_index('ix_provider_usage_events_job_id', table_name='provider_usage_events')
    op.drop_index('ix_provider_usage_events_user_id', table_name='provider_usage_events')
    op.drop_table('provider_usage_events')

    op.drop_index('ix_user_quotas_user_id', table_name='user_quotas')
    op.drop_table('user_quotas')

    op.drop_index('ix_research_jobs_user_created', table_name='research_jobs')
    op.drop_index('ix_research_jobs_user_status', table_name='research_jobs')
    op.drop_index('ix_research_jobs_client_token', table_name='research_jobs')
    op.drop_column('research_jobs', 'client_token')

