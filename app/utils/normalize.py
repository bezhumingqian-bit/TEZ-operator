"""状态归一化工具：把上游平台的中文/脏 status 收敛到标准英文值。

单一来源（Single Source of Truth）：所有状态映射集中在此，
采集层（BrowserImpl）和聚合层（HostService）统一引用，避免三处重复定义。
"""

from __future__ import annotations

import re

from app.utils.logger import get_logger

log = get_logger(__name__)

#: 中文状态 → 英文标准值 的映射表
STATUS_MAP_CN_TO_EN: dict[str, str] = {
    "运营中": "online",
    "在线": "online",
    "维护中": "maintenance",
    "维修中": "maintenance",
    "待运营": "maintenance",
    "待上线": "maintenance",
    "故障": "offline",
    "离线": "offline",
    "下线": "offline",
}

#: 合法的标准状态值集合
VALID_STATUSES: frozenset[str] = frozenset({"online", "offline", "maintenance"})


def normalize_status(raw: str | None) -> str | None:
    """把任意来源的 status 收敛到 ``online/offline/maintenance``。

    处理流程：
    1. 已是合法英文 → 直接返回
    2. 带箭头前缀 ``--->`` / 方括号标注 ``[...]`` → 清洗后再匹配
    3. 中文映射命中 → 翻译为英文
    4. 其他未知值 → 记 warning 并返回 ``None``

    真实格式示例::

        --->运营中[需告警]
        运营中
        维护中

    Args:
        raw: 上游原始状态字符串，可能为 ``None``。

    Returns:
        标准英文状态值，或 ``None``（无法识别时）。
    """
    if not raw:
        return None

    v = raw.strip()
    if v in VALID_STATUSES:
        return v

    # 清洗箭头前缀和方括号标注
    v = re.sub(r"^[-=>{>]*", "", v).strip()
    v = re.sub(r"\[.*?\]", "", v).strip()
    if not v:
        return None

    if v in VALID_STATUSES:
        return v
    if v in STATUS_MAP_CN_TO_EN:
        return STATUS_MAP_CN_TO_EN[v]

    log.warning("normalize.unknown_status", value=raw)
    return None
