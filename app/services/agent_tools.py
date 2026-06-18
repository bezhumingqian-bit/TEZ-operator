"""AI Agent 可调用的工具函数定义与执行器。

所有查询只走本地 DB/缓存，不触发 CMDB/TCUM/IDC 浏览器自动化。
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_host_service
from app.services.knowledge_service import KnowledgeService
from app.utils.logger import get_logger

log = get_logger(__name__)


# ─────────────────────────── Tool Schemas (OpenAI 格式) ───────────────────────────

TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "query_host",
            "description": (
                "根据固资号（TYSV 开头）或内网 IP 查询机器的详细信息。"
                "只查本地数据库(7 天内缓存)，返回可用区、机房、机位、机型、状态、负责人等。"
                "当用户提到具体某台机器、固资号、IP 时调用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "asset_id": {
                        "type": "string",
                        "description": "固资号，例如 TYSV20061X2A。优先用此字段。",
                    },
                    "ip": {
                        "type": "string",
                        "description": "内网 IP，例如 10.0.0.5",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": (
                "在 TEZ 运维知识库中全文搜索，返回匹配的文章题目、摘要和完整内容。"
                "当用户问'怎么操作'、'找谁处理'、'流程是什么'、'迁移/搬迁/投放SOP'时调用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词，从用户问题中提炼。例如'母机故障'、'CMDB权限申请'、'搬迁流程'",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回条数，默认 5",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_zones",
            "description": (
                "列出当前所有可用的边缘可用区(zone)名称和数量。"
                "当用户问'有哪些可用区'、'支持哪些节点'时调用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_zone_detail",
            "description": (
                "查询某个可用区的资源详情，包括机位总数、空闲机位数、在线设备数、"
                "离线设备数、已用机位数等。当用户问'某可用区有多少机位/设备/空闲位'时调用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "zone": {
                        "type": "string",
                        "description": "可用区名称，例如'沈阳边缘一区'、'上海边缘三区（联通）'",
                    },
                },
                "required": ["zone"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_my_workorders",
            "description": (
                "查询我的工单列表（搬迁单、投放单等），可按状态过滤。"
                "当用户问'我的工单'、'最近工单'、'多少单'时调用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "工单状态过滤：pending/processing/done/cancelled，不传则返回全部",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回条数，默认 10",
                        "default": 10,
                    },
                },
                "required": [],
            },
        },
    },
]


# ─────────────────────────── Tool Executors ───────────────────────────


async def exec_query_host(args: dict, session: AsyncSession | None = None) -> dict:
    """执行主机查询(仅本地 DB)。"""
    asset_id = (args.get("asset_id") or "").strip()
    ip = (args.get("ip") or "").strip()
    if not asset_id and not ip:
        return {"ok": False, "error": "asset_id 和 ip 至少需要提供一个"}

    svc = get_host_service()
    try:
        if asset_id:
            host = await svc.get_host_local(asset_id.upper())
        else:
            host = await svc.get_host_by_ip_local(ip)
    except Exception as exc:  # noqa: BLE001
        log.warning("agent.query_host_error", error=str(exc))
        return {"ok": False, "error": f"查询失败: {str(exc)[:200]}"}

    if host is None:
        return {
            "ok": False,
            "error": (
                f"本地数据库中未找到({asset_id or ip})。"
                f"Agent 仅查本地缓存(7 天内有效)，如需最新数据请到'主机查询'页面手动查询"
            ),
        }

    return {
        "ok": True,
        "data_source": "local_db",
        "last_sync_at": host.meta.last_sync_at.isoformat() if host.meta.last_sync_at else None,
        "host": {
            "asset_id": host.asset_id,
            "ip": host.ip,
            "zone": host.zone,
            "machine_type": host.machine_type,
            "status": host.status,
            "idc": host.idc,
            "cabinet": host.cabinet,
            "position": host.position,
            "module": host.module,
            "customer": host.customer,
            "owner": host.owner,
            "backup_owners": host.backup_owners or [],
            "city": host.city,
        },
    }


async def exec_search_knowledge(args: dict, session: AsyncSession | None = None) -> dict:
    """执行知识库全文搜索（包含文章正文）。"""
    if session is None:
        return {"ok": False, "error": "知识库查询需要 DB session"}
    query = (args.get("query") or "").strip()
    limit = min(int(args.get("limit") or 5), 10)
    if not query:
        return {"ok": False, "error": "query 不能为空"}

    svc = KnowledgeService(session)
    try:
        results = await svc.search(query)
    except Exception as exc:  # noqa: BLE001
        log.warning("agent.search_kb_error", error=str(exc))
        return {"ok": False, "error": f"搜索失败: {str(exc)[:200]}"}

    articles = []
    for a in results.get("articles", [])[:limit]:
        content = (a.content or "").strip()
        articles.append({
            "id": a.id,
            "title": a.title,
            "category": a.category,
            "summary": a.summary,
            "tags": a.tags,
            "content": content[:2000],  # 正文最多 2000 字
            "truncated": len(content) > 2000,
        })

    faqs = []
    for f in results.get("faqs", [])[:limit]:
        answer = (f.answer or "").strip()
        faqs.append({
            "id": f.id,
            "question": f.question,
            "category": f.category,
            "answer": answer[:1000],
            "truncated": len(answer) > 1000,
        })

    links = [
        {"name": lnk.name, "purpose": lnk.purpose, "url": lnk.url}
        for lnk in results.get("links", [])[:limit]
    ]

    return {
        "ok": True,
        "total": results.get("total", 0),
        "articles": articles,
        "faqs": faqs,
        "links": links,
    }


async def exec_list_zones(args: dict, session: AsyncSession | None = None) -> dict:
    """列出可用区。"""
    svc = get_host_service()
    try:
        zones = await svc.list_zones()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"查询失败: {str(exc)[:200]}"}
    return {"ok": True, "zones": zones, "count": len(zones)}


async def exec_get_zone_detail(args: dict, session: AsyncSession | None = None) -> dict:
    """查询可用区资源详情(机位/设备等)。"""
    zone = (args.get("zone") or "").strip()
    if not zone:
        return {"ok": False, "error": "zone 不能为空"}

    if session is None:
        return {"ok": False, "error": "需要 DB session"}

    try:
        from app.services.zone_resource_service import ZoneResourceService

        svc = ZoneResourceService(session)
        data = await svc.get_zone_overview(zone, force_refresh=False)
    except Exception as exc:  # noqa: BLE001
        log.warning("agent.zone_detail_error", error=str(exc))
        return {"ok": False, "error": f"查询失败: {str(exc)[:200]}"}

    if not data or not data.get("zone"):
        return {"ok": False, "error": f"未找到可用区 '{zone}'，可能未同步数据"}

    # 裁剪：设备列表截断，避免超长
    online_devices = data.get("online_devices", [])
    offline_devices = data.get("offline_devices", [])

    return {
        "ok": True,
        "zone": {
            "name": data.get("zone"),
            "idc": data.get("idc"),
            "total_positions": data.get("total_positions"),
            "free_count": data.get("free_count"),
            "used_count": data.get("used_count"),
            "total_assets": data.get("total_assets"),
            "online_count": data.get("online_count"),
            "offline_count": data.get("offline_count"),
            "online_devices": online_devices[:20],
            "offline_devices": offline_devices[:20],
            "devices_truncated": (len(online_devices) + len(offline_devices)) > 40,
            "last_sync_at": data.get("last_sync_at"),
            "from_cache": data.get("from_cache", False),
        },
    }


async def exec_list_my_workorders(args: dict, session: AsyncSession | None = None) -> dict:
    """查询工单列表（本地 DB）。"""
    if session is None:
        return {"ok": False, "error": "需要 DB session"}

    status = (args.get("status") or "").strip()
    limit = min(int(args.get("limit") or 10), 20)

    try:
        from sqlalchemy import select

        from app.models.workorder import WorkOrder

        stmt = select(WorkOrder).order_by(WorkOrder.created_at.desc())
        if status:
            stmt = stmt.where(WorkOrder.status == status)
        stmt = stmt.limit(limit)

        result = await session.execute(stmt)
        orders = result.scalars().all()

        return {
            "ok": True,
            "total": len(orders),
            "workorders": [
                {
                    "id": o.id,
                    "order_no": o.order_no,
                    "title": o.title,
                    "status": o.status,
                    "order_type": o.order_type,
                    "detail": o.detail or {},
                    "created_at": o.created_at.isoformat() if o.created_at else None,
                }
                for o in orders
            ],
        }
    except Exception as exc:  # noqa: BLE001
        log.warning("agent.workorders_error", error=str(exc))
        return {"ok": False, "error": f"查询失败: {str(exc)[:200]}"}


# 注册表
TOOL_EXECUTORS: dict[str, Callable[[dict, AsyncSession | None], Awaitable[dict]]] = {
    "query_host": exec_query_host,
    "search_knowledge": exec_search_knowledge,
    "list_zones": exec_list_zones,
    "get_zone_detail": exec_get_zone_detail,
    "list_my_workorders": exec_list_my_workorders,
}
