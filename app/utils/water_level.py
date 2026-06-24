# -*- coding: utf-8 -*-
"""机位水位指标计算工具 — 单一来源模块。

阈值定义在这里，禁止在前端或业务代码中硬编码水位规则。
"""

from __future__ import annotations

from typing import Any

# ─── 水位阈值常量（可调整的唯一位置）─��─

# 空闲率 < 5% 视为「紧张」
CRITICAL_FREE_RATE: float = 0.05

# 空闲率 < 15% 或空闲机位 ≤ 3 视为「预警」
WARNING_FREE_RATE: float = 0.15
WARNING_FREE_ABS: int = 3


def calc_water_level(
    total: int,
    free: int,
    used: int,
    online: int,
    offline: int,
) -> dict[str, Any]:
    """根据可用区快照数据计算水位指标。

    Args:
        total:  总机位数
        free:   空闲机位数
        used:   已用机位数
        online: 在线设备数
        offline: 离线设备数

    Returns:
        包含 usage_rate / free_rate / offline_rate / level / level_label 的 dict，
        total <= 0 时返回 unknown 状态，不抛异常。
    """
    # 防御 None 值（ORM default=0 保证不出现，但对抗性防御）
    total = total or 0
    free = free or 0
    used = used or 0
    online = online or 0
    offline = offline or 0

    if total <= 0:
        return {
            "usage_rate": 0.0,
            "free_rate": 0.0,
            "offline_rate": 0.0,
            "level": "unknown",
            "level_label": "无数据",
        }

    usage_rate = round(used / total, 4)
    free_rate = round(free / total, 4)

    device_total = online + offline
    offline_rate = round(offline / device_total, 4) if device_total > 0 else 0.0

    # 分级判定（空闲率为主要指标，绝对值兜底）
    if free == 0 or free_rate < CRITICAL_FREE_RATE:
        level = "critical"
        level_label = "紧张"
    elif free_rate < WARNING_FREE_RATE or free <= WARNING_FREE_ABS:
        level = "warning"
        level_label = "预警"
    else:
        level = "healthy"
        level_label = "健康"

    return {
        "usage_rate": usage_rate,
        "free_rate": free_rate,
        "offline_rate": offline_rate,
        "level": level,
        "level_label": level_label,
    }
