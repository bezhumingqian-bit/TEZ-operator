"""IDCRM Mock 实现。"""

from __future__ import annotations

from typing import Any


class IDCRMMockImpl:
    name = "idcrm-mock"

    async def get_position(
        self,
        idc: str,
        cabinet: str | None = None,
        asset_id: str | None = None,
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

    async def close(self) -> None:
        return None
