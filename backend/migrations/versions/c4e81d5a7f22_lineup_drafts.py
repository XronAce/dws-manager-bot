"""war_lineups: per-officer drafts alongside the published plan

Revision ID: c4e81d5a7f22
Revises: a1c7f3b920e4
Create Date: 2026-09-04 11:05:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = 'c4e81d5a7f22'
down_revision = 'a1c7f3b920e4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('war_lineups', sa.Column('owner_id', sa.BigInteger(), nullable=True))
    op.add_column('war_lineups', sa.Column('owner_name', sa.String(length=100), nullable=True))
    op.add_column('war_lineups', sa.Column('title', sa.String(length=80), nullable=True))
    op.create_index('ix_war_lineups_owner_id', 'war_lineups', ['owner_id'])

    # The map generator's first release wrote to "default"; there is one published
    # plan and it is now called "official". Rename rather than orphan it.
    op.execute("UPDATE war_lineups SET slug = 'official' WHERE slug = 'default'")


def downgrade() -> None:
    op.execute("UPDATE war_lineups SET slug = 'default' WHERE slug = 'official'")
    op.drop_index('ix_war_lineups_owner_id', table_name='war_lineups')
    op.drop_column('war_lineups', 'title')
    op.drop_column('war_lineups', 'owner_name')
    op.drop_column('war_lineups', 'owner_id')
