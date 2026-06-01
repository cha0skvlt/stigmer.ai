"""Stigmergy 3/3: per-agent API keys and audit log (depends on concurrency schema).

Revision ID: 004_stigmergy_agents
Revises: 003_stigmergy_concurrency
Create Date: 2026-06-01
"""

from alembic import op

revision = "004_stigmergy_agents"
down_revision = "003_stigmergy_concurrency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE agents (
            agent_id      TEXT PRIMARY KEY,
            key_hash      TEXT NOT NULL,
            name          TEXT NOT NULL,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            last_seen_at  TIMESTAMPTZ
        );
        """
    )

    op.execute(
        """
        CREATE TABLE agent_events (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            agent_id    TEXT NOT NULL REFERENCES agents(agent_id) ON DELETE CASCADE,
            action      TEXT NOT NULL,
            card_id     TEXT REFERENCES cards(id) ON DELETE SET NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )
    op.execute("CREATE INDEX idx_agent_events_created ON agent_events (created_at DESC);")

    op.execute(
        """
        CREATE OR REPLACE FUNCTION notify_board_change() RETURNS trigger AS $$
        BEGIN
            PERFORM pg_notify('board.changed', json_build_object(
                'op', TG_OP,
                'table', TG_TABLE_NAME,
                'id', COALESCE(
                    to_jsonb(NEW)->>'id',
                    to_jsonb(OLD)->>'id',
                    to_jsonb(NEW)->>'card_id',
                    to_jsonb(OLD)->>'card_id',
                    to_jsonb(NEW)->>'agent_id',
                    to_jsonb(OLD)->>'agent_id'
                )
            )::text);
            RETURN COALESCE(NEW, OLD);
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        DROP TRIGGER IF EXISTS agent_events_notify ON agent_events;
        CREATE TRIGGER agent_events_notify
            AFTER INSERT ON agent_events
            FOR EACH ROW EXECUTE FUNCTION notify_board_change();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS agent_events_notify ON agent_events;")
    op.execute("DROP TABLE IF EXISTS agent_events;")
    op.execute("DROP TABLE IF EXISTS agents;")
