"""数全通（IDCRM）客户端（HTTP + Mock）。

负责：机房 + 机柜 → 机位 / TPC 信息。
"""

from __future__ import annotations

from typing import Any

from app.clients.base import BaseHTTPClient
from app.config import get_settings


class IDCRMClient(BaseHTTPClient):
    name = "idcrm"

    def __init__(self, mock_mode: bool | None = None) -> None:
        s = get_settings()
        super().__init__(
            base_url=s.idcrm_base_url,
            token=s.idcrm_token,
            timeout=s.idcrm_timeout,
            mock_mode=s.idcrm_mock_mode if mock_mode is None else mock_mode,
        )

    # ──────────────── public ────────────────

    async def get_position(
        self,
        idc: str,
        cabinet: str | None = None,
        asset_id: str | None = None,
    ) -> dict[str, Any] | None:
        """根据机房 + 机柜（或固资号）查机位。"""

        if self.mock_mode:
            return self._mock_position(idc, cabinet, asset_id)
        raise NotImplementedError("IDCRM 真实模式待 W2 接入（Q3 解决后）")

    # ──────────────── mock ────────────────

    def _mock_position(
        self,
        idc: str,
        cabinet: str | None,
        asset_id: str | None,
    ) -> dict[str, Any] | None:
        if not idc:
            return None
        cab = cabinet or "A-12"
        # 用 asset_id 末位生成机位号
        seat = "3"
        if asset_id:
            seat = str((sum(ord(c) for c in asset_id) % 40) + 1)
        return {
            "idc": idc,
            "cabinet": cab,
            "position": f"{cab}-{seat}",
            "has_tpc": True,
            "_source": "idcrm-mock",
        }
