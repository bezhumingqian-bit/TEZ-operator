"""xlsx 导出服务（W3 Day 4）。

设计：
- 用 ``openpyxl`` 在内存里生成 xlsx（W1 已在 requirements）
- 表头中文化，列序与 ``HostInfo`` 主体字段一致
- 通过 FastAPI ``StreamingResponse`` 流式返回，避免大文件 OOM
- 文件名按 UTC 时间戳生成

数据安全：
- mock / 真实数据共用同一段代码路径，不在导出层做特殊脱敏
- 真实数据的脱敏责任在采集层（CCDB/TCUM/IDCRM 客户端）
"""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO

from fastapi.responses import StreamingResponse
from openpyxl import Workbook

from app.schemas.host import HostInfo

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# ── 表头与字段对照（与前端展示列对齐）──
# (字段名, 中文表头, 取值函数)
COLUMNS: list[tuple[str, str]] = [
    ("asset_id", "固资号"),
    ("ip", "IP"),
    ("machine_type", "机型"),
    ("use_years", "使用年限"),
    ("status", "状态"),
    ("idc", "机房"),
    ("cabinet", "机柜"),
    ("position", "机位"),
    ("module", "模块"),
    ("customer", "客户"),
    ("owner", "主负责人"),
    ("backup_owners", "备份联系人"),
    ("zone", "Zone"),
    ("city", "城市"),
    ("server_type", "Server类型"),
    ("app_id", "AppID"),
    ("has_tpc", "TPC"),
]


def _cell_value(host: HostInfo, field: str) -> object:
    """把 HostInfo 的字段转成 xlsx 单元格能写入的标量。"""
    v = getattr(host, field, None)
    if v is None:
        return ""
    if isinstance(v, list):
        # 备份联系人 list[str] → 分号分隔
        return ";".join(str(x) for x in v)
    if isinstance(v, dict):
        return ",".join(f"{k}={vv}" for k, vv in v.items())
    if isinstance(v, bool):
        return "是" if v else "否"
    return v


def build_hosts_xlsx(hosts: list[HostInfo], filename: str | None = None) -> StreamingResponse:
    """根据 HostInfo 列表构造 xlsx StreamingResponse。

    Args:
        hosts: 主机列表（已经过 service 融合 + 脱敏）
        filename: 自定义文件名；不传则按 UTC 时间戳生成
    """

    wb = Workbook()
    ws = wb.active
    ws.title = "hosts"

    # 表头
    ws.append([cn for _, cn in COLUMNS])
    # 数据行
    for h in hosts:
        ws.append([_cell_value(h, field) for field, _ in COLUMNS])

    # 简单列宽
    for col_idx in range(1, len(COLUMNS) + 1):
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = 18

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)

    if not filename:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")  # noqa: UP017
        filename = f"hosts_{ts}.xlsx"

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
    }
    return StreamingResponse(buf, media_type=XLSX_MIME, headers=headers)


__all__ = ["build_hosts_xlsx", "XLSX_MIME", "COLUMNS"]
