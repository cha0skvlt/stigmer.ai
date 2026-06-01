"""Stigmergy 1/3: card version + lease fields for multi-agent concurrency.

Revision ID: 003_stigmergy_concurrency
Revises: 002_label_tone_colors
Create Date: 2026-06-01
"""

from alembic import op

revision = "003_stigmergy_concurrency"
down_revision = "002_label_tone_colors"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE cards
            ADD COLUMN version INT NOT NULL DEFAULT 0,
            ADD COLUMN claimed_by TEXT,
            ADD COLUMN claimed_at TIMESTAMPTZ,
            ADD COLUMN lease_expires_at TIMESTAMPTZ;
        """
    )
    op.execute(
        """
        CREATE INDEX idx_cards_claimable ON cards (claimed_by, lease_expires_at);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_cards_claimable;")
    op.execute(
        """
        ALTER TABLE cards
            DROP COLUMN IF EXISTS lease_expires_at,
            DROP COLUMN IF EXISTS claimed_at,
            DROP COLUMN IF EXISTS claimed_by,
            DROP COLUMN IF EXISTS version;
        """
    )
