"""TEZ 设备分类器：根据模块名判断设备是否属于 TEZ 及当前状态。

单一来源（Single Source of Truth）：把分散在 routers/hosts.py 和
services/zone_resource_service.py 中的分类逻辑集中到这里，避免修改时漏改。
"""

from __future__ import annotations

from typing import TypedDict


class DeviceClassification(TypedDict):
    """设备分类结果。"""

    is_tez: bool
    is_transitional: bool
    reason: str | None


#: 明确标识 TEZ 设备的核心关键词
TEZ_CORE_KEYWORDS: tuple[str, ...] = ("腾讯云边缘可用区", "TEZ")

#: 标识设备处于过渡状态的关键词（搬迁/待上线/buffer 等）
TRANSITIONAL_KEYWORDS: tuple[str, ...] = (
    "待上线",
    "上线中",
    "搬迁",
    "待搬迁",
    "buffer",
    "未上线",
)

#: 边缘计算模块标识
EDGE_COMPUTE_MARKER: str = "边缘计算"


def classify_device(module: str, status: str | None = None) -> DeviceClassification:
    """根据模块名和设备状态判断设备分类。

    判定规则（与 hosts.py / zone_resource_service.py 保持一致）：
    1. 模块含 ``腾讯云边缘可用区`` 或 ``TEZ`` → **是 TEZ**
    2. 模块含 ``边缘计算`` + 过渡关键词 → **是 TEZ**（过渡中）
    3. 其他 → **非 TEZ**

    对于 TEZ 设备，进一步判断：
    - 含过渡关键词 → ``is_transitional=True``，并推导原因
    - 状态为 ``online`` → 已上线
    - 其他 → 按状态推导原因

    Args:
        module: 设备所属模块名。
        status: 设备标准状态（``online/offline/maintenance`` 或 ``None``）。

    Returns:
        :class:`DeviceClassification` 字典，包含 ``is_tez``、``is_transitional``、``reason``。
    """
    module_lower = module.lower()

    is_core_tez = any(kw in module for kw in TEZ_CORE_KEYWORDS)
    has_edge_compute = EDGE_COMPUTE_MARKER in module
    is_transitional = any(kw in module for kw in TRANSITIONAL_KEYWORDS) or "buffer" in module_lower

    if is_core_tez:
        is_tez = True
    elif has_edge_compute and is_transitional:
        is_tez = True
    else:
        is_tez = False

    if not is_tez:
        return DeviceClassification(is_tez=False, is_transitional=False, reason=None)

    # TEZ 设备：推导原因
    reason = _derive_reason(module, status, is_transitional)
    return DeviceClassification(is_tez=True, is_transitional=is_transitional, reason=reason)


def _derive_reason(module: str, status: str | None, is_transitional: bool) -> str:
    """根据模块名和状态推导未上线原因（内部辅助函数）。"""
    module_lower = module.lower()

    if is_transitional:
        if "待上线" in module or "未上线" in module:
            return "模块状态：待上线"
        if "上线中" in module:
            return "模块状态：上线中"
        if "搬迁" in module:
            return "模块状态：搬迁中"
        if "待搬迁" in module:
            return "模块状态：待搬迁"
        if "buffer" in module_lower:
            return "模块状态：buffer（待分配）"
        return "模块状态：过渡中"

    if status == "online":
        return ""

    if status == "maintenance":
        return "设备状态：维护中"
    if status == "offline":
        return "设备状态：离线/故障"

    return f"设备状态：{status or '未知'}"
