"""Add five more default label colors (10 tones total).

Revision ID: 002_label_tone_colors
Revises: 001_initial
Create Date: 2026-05-28
"""

from alembic import op

revision = "002_label_tone_colors"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO labels (slug, name, tone, emoji, description)
        VALUES
          ('teal', 'Design', 'teal', '🔷', NULL),
          ('pink', 'Feature', 'pink', '🩷', NULL),
          ('gray', 'Low', 'gray', '⚪', NULL),
          ('lime', 'Quick', 'lime', '⚡', NULL),
          ('indigo', 'Research', 'indigo', '🔮', NULL)
        ON CONFLICT (slug) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM card_labels
        WHERE label_id IN (SELECT id FROM labels WHERE slug IN ('teal', 'pink', 'gray', 'lime', 'indigo'));
        DELETE FROM labels WHERE slug IN ('teal', 'pink', 'gray', 'lime', 'indigo');
        """
    )
