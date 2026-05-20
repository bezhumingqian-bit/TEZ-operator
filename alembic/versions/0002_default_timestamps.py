"""default timestamps for host_history / audit_logs

Revision ID: 0002_default_timestamps
Revises: 0001_initial
Create Date: 2026-05-20 10:00:00

reviewer 建议-4：host_history.created_at / audit_logs.created_at 缺 server_default，
INSERT 时不显式赋值会触发 ``Field 'created_at' doesn't have a default value`` 错误。
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_default_timestamps"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "host_history",
        "created_at",
        existing_type=sa.DateTime(),
        existing_nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    op.alter_column(
        "audit_logs",
        "created_at",
        existing_type=sa.DateTime(),
        existing_nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )


def downgrade() -> None:
    op.alter_column(
        "audit_logs",
        "created_at",
        existing_type=sa.DateTime(),
        existing_nullable=False,
        server_default=None,
    )
    op.alter_column(
        "host_history",
        "created_at",
        existing_type=sa.DateTime(),
        existing_nullable=False,
        server_default=None,
    )
