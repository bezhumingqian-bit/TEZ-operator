"""TCUM Mock 实现 —— 不发请求，返回固定虚构数据，供测试 / 本地无凭据联调使用。

注意：所有数据严格遵循 docs/16-数据安全规则.md，使用占位值（customer_a / 10.0.x.x / 示例机房A1）。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


class TCUMMockImpl:
    """TCUM mock 数据返回器。"""

    name = "tcum-mock"

    @staticmethod
    def _mock_history() -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)  # noqa: UP017
        return [
            {
                "event_type": "投放",
                "event_at": (now - timedelta(days=300)).isoformat(),
                "to_module": "ten1.customer_a-PRD",
                "source": "tcum",
                "description": "TEZ 示例机房 A1 首批投放",
            },
            {
                "event_type": "迁入",
                "event_at": (now - timedelta(days=560)).isoformat(),
                "from_module": "ECM",
                "to_module": "TEZ",
                "source": "tcum",
                "description": "由 ECM 迁入 TEZ",
            },
            {
                "event_type": "入库",
                "event_at": (now - timedelta(days=730)).isoformat(),
                "source": "tcum",
                "description": "首次入库",
            },
        ]

    async def get_by_asset(self, asset_id: str) -> dict[str, Any] | None:
        if not asset_id:
            return None
        return {
            "asset_id": asset_id.upper(),
            "ip": "10.0.0.5",
            "idc": "示例机房A1",
            "cabinet": "A-12",
            "machine_type": "MOCK-1G",
            "history": self._mock_history(),
            "_source": "tcum-mock",
        }

    async def search_by_ip(self, ip: str) -> dict[str, Any] | None:
        if not ip:
            return None
        return {
            "asset_id": "TYSV00000001",  # mock 示例 ID,非真实固资号
            "ip": ip,
            "idc": "示例机房A1",
            "cabinet": "A-12",
            "machine_type": "MOCK-1G",
            "history": self._mock_history(),
            "_source": "tcum-mock",
        }

    async def close(self) -> None:
        return None
