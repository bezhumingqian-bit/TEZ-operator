"""initial schema: host_cache / host_history / audit_logs

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-19 19:00:00

"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "host_cache",
        sa.Column("asset_id", sa.String(length=64), nullable=False),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("zone", sa.String(length=64), nullable=True),
        sa.Column("machine_type", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("idc", sa.String(length=64), nullable=True),
        sa.Column("cabinet", sa.String(length=64), nullable=True),
        sa.Column("position", sa.String(length=64), nullable=True),
        sa.Column("module", sa.String(length=128), nullable=True),
        sa.Column("customer", sa.String(length=64), nullable=True),
        sa.Column("app_id", sa.String(length=64), nullable=True),
        sa.Column("has_tpc", sa.Boolean(), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("asset_id", name=op.f("pk_host_cache")),
    )
    op.create_index("ix_host_cache_ip", "host_cache", ["ip"], unique=False)
    op.create_index("ix_host_cache_zone", "host_cache", ["zone"], unique=False)
    op.create_index("ix_host_cache_module", "host_cache", ["module"], unique=False)

    op.create_table(
        "host_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("asset_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("event_at", sa.DateTime(), nullable=False),
        sa.Column("from_module", sa.String(length=128), nullable=True),
        sa.Column("to_module", sa.String(length=128), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "source",
            sa.String(length=32),
            nullable=True,
            comment="cmdb/tcum/manual",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_host_history")),
    )
    op.create_index("ix_host_history_asset_id", "host_history", ["asset_id"], unique=False)

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=True),
        sa.Column(
            "action",
            sa.String(length=64),
            nullable=False,
            comment="search/export/...",
        ),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audit_logs_user_id", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_host_history_asset_id", table_name="host_history")
    op.drop_table("host_history")
    op.drop_index("ix_host_cache_module", table_name="host_cache")
    op.drop_index("ix_host_cache_zone", table_name="host_cache")
    op.drop_index("ix_host_cache_ip", table_name="host_cache")
    op.drop_table("host_cache")
