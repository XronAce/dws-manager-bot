"""war_lineups — the shared Pass Occupation War line-up

Revision ID: a1c7f3b920e4
Revises: 336684047c8f
Create Date: 2026-09-04 09:40:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'a1c7f3b920e4'
down_revision = '336684047c8f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'war_lineups',
        sa.Column('slug', sa.String(length=64), nullable=False),
        sa.Column('order', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('mercs', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('opts', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('updated_by_id', sa.BigInteger(), nullable=True),
        sa.Column('updated_by_name', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('slug'),
    )


def downgrade() -> None:
    op.drop_table('war_lineups')
