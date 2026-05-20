"""CCDB Mock 实现 —— 数据严格脱敏（参考 docs/16）。"""

from __future__ import annotations

from typing import Any


class CCDBMockImpl:
    """CCDB mock 数据返回器。"""

    name = "ccdb-mock"

    async def get_by_asset(self, asset_id: str) -> dict[str, Any] | None:
        if not asset_id:
            return None
        # 固资号末位决定客户，做点变化
        suffix = asset_id[-1].upper()
        customer_map = {"A": "customer_a", "P": "customer_a", "R": "customer_b", "Z": "customer_c"}
        customer = customer_map.get(suffix, "customer_a")
        return {
            "asset_id": asset_id.upper(),
            "ip": f"10.0.{(ord(suffix) % 200) + 1}.1",
            "zone": "zone_a",
            "module": f"ten1.{customer}-PRD",
            "customer": customer,
            "app_id": "0000000000",
            "status": "online",
            "machine_type": "MOCK-1G",
            "has_tpc": True,
            "billing_tags": {"tag_a": "1"},
            "_source": "ccdb-mock",
        }

    async def get_by_ip(self, ip: str) -> dict[str, Any] | None:
        if not ip:
            return None
        return {
            "asset_id": "TYSV00000001",  # mock 示例 ID,非真实固资号
            "ip": ip,
            "zone": "zone_a",
            "module": "ten1.customer_a-PRD",
            "customer": "customer_a",
            "app_id": "0000000000",
            "status": "online",
            "machine_type": "MOCK-1G",
            "has_tpc": True,
            "billing_tags": {"tag_a": "1"},
            "_source": "ccdb-mock",
        }

    async def list_by_zone(self, zone: str, limit: int = 100) -> list[dict[str, Any]]:
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
                "machine_type": "MOCK-1G",
                "has_tpc": True,
                "billing_tags": {"tag_a": "1"},
                "_source": "ccdb-mock",
            }
            for i in range(n)
        ]

    async def close(self) -> None:
        return None
