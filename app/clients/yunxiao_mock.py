"""云霄平台 — Mock 数据。"""

from __future__ import annotations

from datetime import datetime


async def mock_query_host_machines(zone: str | None = None, machine_type: str | None = None,
                                   instance_family: str | None = None) -> list[dict]:
    """Mock: 母机管理查询。"""
    zone_val = zone or "广州三区"
    return [
        {
            "asset_id": "TYSV16010803",
            "ip": "10.59.158.157",
            "instance_family": "S1",
            "device_type": "VSELF",
            "zone": zone_val,
            "logical_zone": "1",
            "pool": "qcloud",
            "sale_pool": "plain",
            "module_label": f"广州-华新园-M{1 if not machine_type else ''}",
            "cpu_available": 10,
            "cpu_total": 56,
            "mem_available": 32,
            "mem_total": 96,
            "gpu_available": 0,
            "gpu_total": 0,
            "disk_available": 2600,
            "disk_total": 2600,
            "local_disk_available": 0,
            "local_disk_total": 0,
            "is_empty_host": "否",
            "is_cdh": "是",
            "exclusive_owner": "-",
            "tags": "",
            "machine_model": "M10",
            "health_score": 100,
            "online_status": "ONLINE",
            "kernel_version": "2.6.32-358.VPC_1.12",
            "kernel_version_id": "1",
            "manufacturer_module": "-",
            "sale_pool_type": "plain",
            "box_type": "新装箱",
            "host_updated_at": datetime(2026, 6, 17, 11, 48, 48),
        },
    ]


async def mock_query_inventory(zone: str | None = None, instance_family: str | None = None,
                               instance_type: str | None = None) -> list[dict]:
    """Mock: 新机型库存查询。"""
    zone_val = zone or "广州六区"
    family_val = instance_family or "S5"
    return [
        {
            "zone": zone_val,
            "instance_family": family_val,
            "instance_type": instance_type or "S5.MEDIUM4",
            "status": "已上线",
            "pool": "qcloud",
            "billing_type": "按量计费",
            "inventory": 500,
            "inventory_threshold": 50,
            "safety_quota": 200,
            "cpu": 4,
            "gpu": 0,
            "storage_block": 0,
            "mem": 8192,
            "device_type": "VSELF",
        },
    ]
