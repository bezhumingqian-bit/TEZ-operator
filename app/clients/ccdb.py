"""CCDB 客户端（HTTP + Mock）。

W1：mock 模式返回真实感强的固定数据，便于联调。
W2+：账号到位后实现真实的 CCDB HTTP 调用（参考 docs/02 § 2.3）。
"""

from __future__ import annotations

from typing import Any

from app.clients.base import BaseHTTPClient
from app.config import get_settings


class CCDBClient(BaseHTTPClient):
    """CCDB 接口签名 + Mock 实现。"""

    name = "ccdb"

    def __init__(self, mock_mode: bool | None = None) -> None:
        s = get_settings()
        super().__init__(
            base_url=s.ccdb_base_url,
            token=s.ccdb_token,
            timeout=s.ccdb_timeout,
            mock_mode=s.ccdb_mock_mode if mock_mode is None else mock_mode,
        )

    # ──────────────── public ────────────────

    async def get_by_asset(self, asset_id: str) -> dict[str, Any] | None:
        """按固资号查询单台机的 CCDB 信息。"""

        if self.mock_mode:
            return self._mock_by_asset(asset_id)
        # 真实实现：QueryDeviceInfoByUuid 类的接口
        # data = await self.request("POST", "/", json=self._wrap("QueryDeviceInfoByUuid", {...}))
        # return data.get("data") or None
        raise NotImplementedError("CCDB 真实模式待 W2 接入（账号 Q1 解决后）")

    async def get_by_ip(self, ip: str) -> dict[str, Any] | None:
        """按 IP 反查。"""

        if self.mock_mode:
            return self._mock_by_ip(ip)
        raise NotImplementedError("CCDB 真实模式待 W2 接入")

    async def list_by_zone(self, zone: str, limit: int = 100) -> list[dict[str, Any]]:
        """按 zone 列出母机。"""

        if self.mock_mode:
            return self._mock_by_zone(zone, limit)
        raise NotImplementedError("CCDB 真实模式待 W2 接入")

    # ──────────────── mock ────────────────

    def _mock_by_asset(self, asset_id: str) -> dict[str, Any] | None:
        if not asset_id:
            return None
        # 固资号末位决定客户，做点变化
        suffix = asset_id[-1].upper()
        customer_map = {"A": "customer_a", "P": "customer_a", "R": "customer_b", "Z": "customer_c"}
        customer = customer_map.get(suffix, "customer_a")
        return {
            "asset_id": asset_id.upper(),
            "ip": f"10.0.{(ord(suffix) % 200) + 1}.1",
            "zone": "ap-shanghai-tea-3",
            "module": f"ten1.{customer}-PRD",
            "customer": customer,
            "app_id": "0000000000",
            "status": "online",
            "machine_type": "CG3-10G",
            "has_tpc": True,
            "billing_tags": {"tag_a": "1"},
            "_source": "ccdb-mock",
        }

    def _mock_by_ip(self, ip: str) -> dict[str, Any] | None:
        if not ip:
            return None
        return {
            "asset_id": "TYSV00000001",  # mock 示例 ID,非真实固资号
            "ip": ip,
            "zone": "ap-shanghai-tea-3",
            "module": "ten1.customer_a-PRD",
            "customer": "customer_a",
            "app_id": "0000000000",
            "status": "online",
            "machine_type": "CG3-10G",
            "has_tpc": True,
            "billing_tags": {"tag_a": "1"},
            "_source": "ccdb-mock",
        }

    def _mock_by_zone(self, zone: str, limit: int) -> list[dict[str, Any]]:
        # 生成 5 条假数据，足够 W1 联调
        n = min(5, max(1, limit))
        return [
            {
                "asset_id": f"TYSV2006{i:04X}",
                "ip": f"10.0.{i + 1}.1",
                "zone": zone,
                "module": "ten1.customer_a-PRD" if i % 2 == 0 else "ten1.customer_b-PRD",
                "customer": "customer_a" if i % 2 == 0 else "customer_b",
                "app_id": "0000000000",
                "status": "online" if i < 4 else "maintenance",
                "machine_type": "CG3-10G",
                "has_tpc": True,
                "billing_tags": {"tag_a": "1"},
                "_source": "ccdb-mock",
            }
            for i in range(n)
        ]
