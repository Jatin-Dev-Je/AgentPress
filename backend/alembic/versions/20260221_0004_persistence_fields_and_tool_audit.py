"""persistence fields and tool audit

Revision ID: 20260221_0004
Revises: 20260221_0003
Create Date: 2026-02-21

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260221_0004"
down_revision = "20260221_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("provider", sa.String(length=50), nullable=False, server_default="ollama"))
    op.alter_column("agents", "provider", server_default=None)

    op.add_column("messages", sa.Column("token_count", sa.Integer(), nullable=True))

    op.create_table(
        "tool_call_audit",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("agent_id", sa.String(length=36), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "conversation_id",
            sa.String(length=36),
            sa.ForeignKey("conversations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "tool_call_id",
            sa.String(length=36),
            sa.ForeignKey("tool_calls.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("plugin_id", sa.String(length=255), nullable=False),
        sa.Column("tool_name", sa.String(length=255), nullable=False),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("ok", sa.Boolean(), nullable=False),
        sa.Column("response", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("tool_call_audit")
    op.drop_column("messages", "token_count")
    op.drop_column("agents", "provider")
