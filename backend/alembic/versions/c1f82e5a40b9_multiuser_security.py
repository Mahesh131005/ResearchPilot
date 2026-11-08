"""multiuser_security

Revision ID: c1f82e5a40b9
Revises: be4e82129b04
Create Date: 2026-11-07 21:30:00.000000

"""
import os
import uuid
import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import bcrypt

# revision identifiers, used by Alembic.
revision: str = 'c1f82e5a40b9'
down_revision: Union[str, Sequence[str], None] = 'be4e82129b04'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add new columns to users table
    op.add_column('users', sa.Column('hashed_password', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('role', sa.String(length=50), server_default='user', nullable=False))
    op.add_column('users', sa.Column('tier', sa.String(length=50), server_default='free', nullable=False))
    op.add_column('users', sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False))
    op.add_column('users', sa.Column('must_change_password', sa.Boolean(), server_default='false', nullable=False))

    # 2. Create refresh_tokens table
    op.create_table(
        'refresh_tokens',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('replaced_by_token_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_refresh_tokens_token_hash', 'refresh_tokens', ['token_hash'], unique=True)
    op.create_index('ix_refresh_tokens_user_id', 'refresh_tokens', ['user_id'], unique=False)

    # 3. Data preservation & designated owner creation
    bind = op.get_bind()
    
    # Check if designated admin already exists
    from app.core.config import settings
    admin_email = settings.INITIAL_ADMIN_EMAIL.strip().lower()
    admin_password = settings.INITIAL_ADMIN_PASSWORD
    
    salt = bcrypt.gensalt(rounds=12)
    hashed_pw = bcrypt.hashpw(admin_password.encode("utf-8"), salt).decode("utf-8")
    
    res = bind.execute(sa.text("SELECT id FROM users WHERE email = :email"), {"email": admin_email}).fetchone()
    if res:
        owner_id = res[0]
        # Update admin password & role
        bind.execute(
            sa.text("UPDATE users SET hashed_password = :hpw, role = 'admin', tier = 'enterprise', is_active = true, must_change_password = true WHERE id = :uid"),
            {"hpw": hashed_pw, "uid": owner_id}
        )
    else:
        owner_id = uuid.uuid4()
        bind.execute(
            sa.text("""
                INSERT INTO users (id, email, name, hashed_password, role, tier, is_active, must_change_password, created_at, updated_at)
                VALUES (:id, :email, 'Initial Administrator', :hpw, 'admin', 'enterprise', true, true, now(), now())
            """),
            {"id": owner_id, "email": admin_email, "hpw": hashed_pw}
        )

    # 4. Migrate and backfill all existing unowned documents and jobs safely
    bind.execute(
        sa.text("UPDATE documents SET user_id = :owner_id WHERE user_id IS NULL"),
        {"owner_id": owner_id}
    )
    bind.execute(
        sa.text("UPDATE research_jobs SET user_id = :owner_id WHERE user_id IS NULL"),
        {"owner_id": owner_id}
    )

    # 5. Make hashed_password non-nullable now that all existing users have passwords
    op.alter_column('users', 'hashed_password', nullable=False)

    # 6. Establish safe Foreign Key constraints (ON DELETE RESTRICT to prevent accidental cascade destruction)
    op.create_foreign_key(
        'fk_documents_user_id',
        'documents', 'users',
        ['user_id'], ['id'],
        ondelete='RESTRICT'
    )

    # Re-create research_jobs user foreign key with RESTRICT
    try:
        op.drop_constraint('research_jobs_user_id_fkey', 'research_jobs', type_='foreignkey')
    except Exception:
        pass
    
    op.create_foreign_key(
        'fk_research_jobs_user_id',
        'research_jobs', 'users',
        ['user_id'], ['id'],
        ondelete='RESTRICT'
    )

    # 7. Add performance indexes
    op.create_index('ix_documents_user_id', 'documents', ['user_id'], unique=False, if_not_exists=True)
    op.create_index('ix_research_jobs_user_id', 'research_jobs', ['user_id'], unique=False, if_not_exists=True)


def downgrade() -> None:
    # Drop indexes and foreign keys
    op.drop_index('ix_research_jobs_user_id', table_name='research_jobs', if_exists=True)
    op.drop_index('ix_documents_user_id', table_name='documents', if_exists=True)
    
    op.drop_constraint('fk_research_jobs_user_id', 'research_jobs', type_='foreignkey')
    op.drop_constraint('fk_documents_user_id', 'documents', type_='foreignkey')
    
    # Restore research_jobs user_id nullable foreign key
    op.create_foreign_key(
        'research_jobs_user_id_fkey',
        'research_jobs', 'users',
        ['user_id'], ['id'],
        ondelete='SET NULL'
    )

    # Drop refresh_tokens table
    op.drop_table('refresh_tokens')

    # Drop added users columns
    op.drop_column('users', 'must_change_password')
    op.drop_column('users', 'is_active')
    op.drop_column('users', 'tier')
    op.drop_column('users', 'role')
    op.drop_column('users', 'hashed_password')
