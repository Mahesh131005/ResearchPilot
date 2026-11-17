"""add_byok_tracking_to_research_jobs

Revision ID: f5a11939c2d1
Revises: e3f940182b1c
Create Date: 2026-11-17 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f5a11939c2d1'
down_revision: Union[str, Sequence[str], None] = 'e3f940182b1c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add is_byok column to research_jobs
    op.add_column(
        'research_jobs',
        sa.Column('is_byok', sa.Boolean(), server_default='false', nullable=False)
    )


def downgrade() -> None:
    op.drop_column('research_jobs', 'is_byok')

