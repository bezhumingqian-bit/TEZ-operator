"""TCUM CMDB 客户端（HTTP + Mock）。

负责：固资号 → 物理机房 / 机柜 / 机型 / 投放历史。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.clients.base import BaseHTTPClient
from app.config import get_settings


class TCUMClient(BaseHTTPClient):
    name = "tcum"

    def __init__(self, mock_mode: bool | None = None) -> None:
        s = get_settings()
        super().__init__(
            base_url=s.tcum_base_url,
            token=s.tcum_token,
            timeout=s.tcum_timeout,
            mock_mode=s.tcum_mock_mode if mock_mode is None else mock_mode,
        )

    # ──────────────── public ────────────────

    async def get_by_asset(self, asset_id: str) -> dict[str, Any] | None:
        """按固资号查询机房 / 机柜 / 机型 / 历史。"""

        if self.mock_mode:
            return self._mock_by_asset(asset_id)
        raise NotImplementedError("TCUM 真实模式待 W2 接入（Q2 解决后）")

    async def search_by_ip(self, ip: str) -> dict[str, Any] | None:
        if self.mock_mode:
            return self._mock_by_ip(ip)
        raise NotImplementedError("TCUM 真实模式待 W2 接入")

    # ──────────────── mock ────────────────

    @staticmethod
    def _mock_history() -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
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

    def _mock_by_asset(self, asset_id: str) -> dict[str, Any] | None:
        if not asset_id:
            return None
        return {
            "asset_id": asset_id.upper(),
            "ip": "10.0.0.5",
            "idc": "示例机房A1",
            "cabinet": "A-12",
            "machine_type": "CG3-10G",
            "history": self._mock_history(),
            "_source": "tcum-mock",
        }

    def _mock_by_ip(self, ip: str) -> dict[str, Any] | None:
        if not ip:
            return None
        return {
            "asset_id": "TYSV00000001",  # mock 示例 ID,非真实固资号
            "ip": ip,
            "idc": "示例机房A1",
            "cabinet": "A-12",
            "machine_type": "CG3-10G",
            "history": self._mock_history(),
            "_source": "tcum-mock",
        }
