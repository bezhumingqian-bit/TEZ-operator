"""输入识别工具：把任意输入字符串归类为 asset_id / ip / zone / unknown。"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Literal

QueryType = Literal["asset_id", "ip", "zone", "unknown"]

# 固资号：以 TYSV 起头的字母数字组合（旧资料里也有 TYHA / TYSY 等开头，
# 实际以 TYSV 为主，这里保留宽松匹配，但要求 6 位以上）
ASSET_RE = re.compile(r"^TY[A-Z]{2}[A-Z0-9]{4,}$", re.IGNORECASE)

# 严格的 IPv4：每段 0-255，避免误判
_IP_OCTET = r"(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)"
IP_RE = re.compile(rf"^{_IP_OCTET}(?:\.{_IP_OCTET}){{3}}$")

# Zone：兼容两种格式
#   - 占位格式：zone_a / zone_b / zone_test_1（开发 / mock 用）
#   - 真实格式：ap-<region>-<sub>-<digit>（W4 真实联调用）
# 注意：parser 是输入识别，写得稍宽容；docs/16 § 五 的预提交钩子另有更严的真实
# 固资号 / 内网信息正则。
_ZONE_PLACEHOLDER_RE = re.compile(r"^zone(?:_[a-z0-9]+)+$")
_ZONE_REAL_RE = re.compile(r"^[a-z]{2}-[a-z0-9]+(?:-[a-z0-9]+)+-\d+$")


def _is_zone(s: str) -> bool:
    low = s.lower()
    if _ZONE_PLACEHOLDER_RE.match(low) or _ZONE_REAL_RE.match(low):
        return True
    # 支持真实中文可用区名（如"东莞边缘一区"）
    try:
        from app.data.zone_mapping import ZONE_IDC_MAPPING
        if s in ZONE_IDC_MAPPING:
            return True
    except Exception:
        pass
    # 模糊匹配：含"边缘"+"区"的大概率是zone
    if "边缘" in s and "区" in s:
        return True
    return False


# 兼容旧调用（保留对外 ZONE_RE 名称，但语义改为合并匹配器）
class _ZoneRECompat:
    @staticmethod
    def match(s: str):  # noqa: ANN205 - 仅用 truthy 判断
        return _is_zone(s) or None


ZONE_RE = _ZoneRECompat()


def detect_query_type(q: str | None) -> QueryType:
    """识别输入的查询类型。

    规则优先级：asset_id > ip > zone > unknown
    """

    if q is None:
        return "unknown"
    s = q.strip()
    if not s:
        return "unknown"
    if ASSET_RE.match(s):
        return "asset_id"
    if IP_RE.match(s):
        return "ip"
    if _is_zone(s.lower()):
        return "zone"
    return "unknown"


def normalize_query(q: str) -> str:
    """归一化输入：去空白、固资号大写、zone 小写。"""

    s = q.strip()
    qtype = detect_query_type(s)
    if qtype == "asset_id":
        return s.upper()
    if qtype == "zone":
        return s.lower()
    return s


def split_batch_input(raw: str) -> list[str]:
    """批量输入分隔：支持换行 / 逗号 / 分号 / 空白。

    用于前端粘贴多个固资号的场景；返回去重 + 去空 + 顺序保留的列表。
    """

    if not raw:
        return []
    # 一次性拆出所有 token
    tokens: Iterable[str] = re.split(r"[\s,;]+", raw)
    seen: set[str] = set()
    result: list[str] = []
    for t in tokens:
        n = normalize_query(t)
        if n and n not in seen:
            seen.add(n)
            result.append(n)
    return result
