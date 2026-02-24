"""agent plugin configs

Revision ID: 20260221_0003
Revises: 20260215_0002
Create Date: 2026-02-21

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260221_0003"
down_revision = "20260215_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_plugin_configs",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "agent_id",
            sa.String(length=36),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("plugin_id", sa.String(length=255), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("agent_id", "plugin_id", name="uq_agent_plugin_config"),
    )


def downgrade() -> None:
    op.drop_table("agent_plugin_configs")
