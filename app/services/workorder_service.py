"""工单流服务层。

核心能力：
1. create_order — 创建工单 + 前置校验 + 自动指派
2. transition — 状态流转
3. list/get — 查询
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.workorder import WorkOrder, WorkOrderLog
from app.utils.logger import get_logger

log = get_logger(__name__)

# ─── 状态机 ───
VALID_TRANSITIONS: dict[str, list[str]] = {
    "submitted": ["pending", "rejected"],
    "pending": ["processing", "rejected"],
    "processing": ["verifying", "rejected"],
    "verifying": ["completed", "processing"],  # 验证不通过可打回
    "completed": [],
    "rejected": ["submitted"],  # 驳回后可重新提交
}

# ─── 工单类型 → 默认指派人映射（从 DB 接口人表查询，此处为 fallback）───
# 真实姓名从数据库 contact 表的 responsibility 关系查询
# 以下仅为 fallback 占位（无 DB 时降级用）
DEFAULT_ASSIGNEES: dict[str, str] = {
    "ecm_export": "",  # 运行时从 DB 查"母机重装/投放"分类的主负责人
    "host_deploy": "",
    "migration": "",
    "repair": "",
}

# ─── 前置校验规则 ───
PRE_CHECK_RULES: dict[str, list[str]] = {
    "ecm_export": ["check_tpc", "check_module_path"],
    "host_deploy": ["check_tpc", "check_backup_cleared", "check_module_path"],
    "migration": ["check_target_position", "check_sideband"],
    "repair": [],
}


class WorkOrderService:
    """工单流服务。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ─── 创建工单 ───

    async def create_order(
        self,
        order_type: str,
        title: str,
        creator: str,
        detail: dict[str, Any] | None = None,
        note: str | None = None,
        priority: int = 2,
    ) -> WorkOrder:
        """创建工单：生成编号 → 前置校验 → 自动指派 → 写入。"""

        order_no = await self._gen_order_no()

        # 前置校验
        pre_checks = self._run_pre_checks(order_type, detail or {})

        # 自动指派（从 DB 接口人表查，fallback 为空）
        assignee = await self._resolve_assignee(order_type)

        order = WorkOrder(
            order_no=order_no,
            order_type=order_type,
            title=title,
            status="submitted",
            creator=creator,
            assignee=assignee or None,
            detail=detail,
            pre_checks=pre_checks,
            note=note,
            priority=priority,
        )
        self.session.add(order)
        await self.session.flush()

        # 创建日志
        log_entry = WorkOrderLog(
            order_id=order.id,
            action="create",
            operator=creator,
            content=f"创建工单：{title}",
            from_status=None,
            to_status="submitted",
        )
        self.session.add(log_entry)
        await self.session.flush()

        # 创建即同步到 OnePage 腾讯文档（异步后台任务，不阻塞请求）
        # 重要：提前快照 detail/order_type/title 等字段，避免异步任务执行时
        # session 已关闭导致 ORM 属性访问异常
        if order.order_type in ("migration", "ecm_export", "host_deploy"):
            import asyncio
            push_snapshot = {
                "order_id": order.id,
                "order_no": order.order_no,
                "order_type": order.order_type,
                "title": order.title,
                "priority": order.priority,
                "detail": dict(order.detail) if order.detail else {},
            }
            asyncio.create_task(self._push_to_onepage_safe(push_snapshot))

        return order

    async def _push_to_onepage_safe(self, snapshot: dict) -> None:
        """后台安全推送（异常不影响主流程）。"""
        try:
            await self._push_to_onepage(snapshot)
        except Exception as exc:
            log.warning("workorder.onepage_push_failed", order_id=snapshot.get("order_id"), error=str(exc))

    # ─── 状态流转 ───

    async def transition(
        self, order_id: int, to_status: str, operator: str, comment: str | None = None
    ) -> WorkOrder:
        """状态流转。"""
        order = await self.get_order(order_id)
        if not order:
            raise ValueError(f"工单不存在: {order_id}")

        valid_next = VALID_TRANSITIONS.get(order.status, [])
        if to_status not in valid_next:
            raise ValueError(
                f"非法状态流转: {order.status} → {to_status}（允许: {valid_next}）"
            )

        from_status = order.status
        order.status = to_status

        if to_status == "completed":
            order.completed_at = datetime.now(timezone.utc)

        # 日志
        action_map = {
            "pending": "assign",
            "processing": "process",
            "verifying": "verify",
            "completed": "complete",
            "rejected": "reject",
            "submitted": "resubmit",
        }
        log_entry = WorkOrderLog(
            order_id=order.id,
            action=action_map.get(to_status, "transition"),
            operator=operator,
            content=comment,
            from_status=from_status,
            to_status=to_status,
        )
        self.session.add(log_entry)
        await self.session.flush()

        return order

    async def _push_to_onepage(self, snapshot: dict) -> None:
        """将工单数据推送到 OnePage 腾讯文档。

        接收快照 dict 而非 ORM 对象，确保异步执行时数据可靠。
        """
        from app.skills.tencent_doc_skill import TencentDocSkill

        skill = TencentDocSkill()
        detail = snapshot.get("detail", {})
        order_type = snapshot["order_type"]
        title = snapshot["title"]
        priority = snapshot["priority"]
        order_no = snapshot["order_no"]
        today = datetime.now().strftime("%Y/%m/%d")

        if order_type == "migration":
            data = {
                "date": today,
                "requirement": title,
                "urgent": "是" if priority >= 3 else "否",
                "expected_date": detail.get("expected_date", ""),
                "from_zone": detail.get("source_zone", ""),
                "from_idc": detail.get("source_idc", ""),
                "to_idc": detail.get("target_idc", ""),
                "to_zone": detail.get("zone", ""),
                "quantity": str(detail.get("device_count", "")),
                "device_model": detail.get("vs_type", ""),
                "assets": detail.get("asset_ids", ""),
                "delivery_type": detail.get("delivery_type", "TEZ"),
                "reinstall": "",  # 由 Skill 根据 delivery_type 自动填充
                "target_module": "",  # 由 Skill 根据 delivery_type 自动填充
                "remark": f"工单 {order_no}",
            }
            result = await skill.append_migration_record(data)
        else:
            # ecm_export / host_deploy → 投放记录
            data = {
                "date": today,
                "urgent": "是" if priority >= 3 else "否",
                "type": detail.get("demand_type") or order_type,
                "assets": detail.get("asset_ids", ""),
                "quantity": str(detail.get("device_count", "")),
                "reinstall": detail.get("reinstall", ""),
                "vs_type": detail.get("vs_type", ""),
                "requirement": title,
                "migration_ref": detail.get("migration_ref", ""),
                "zone": detail.get("zone", ""),
                "remark": f"工单 {order_no}",
            }
            result = await skill.append_deployment_record(data)

        log.info(
            "workorder.onepage_push_result",
            order_no=order_no,
            success=result.get("success"),
            data_snapshot={k: v[:20] if isinstance(v, str) and len(v) > 20 else v for k, v in data.items()},
        )
        if not result.get("success"):
            log.warning("workorder.onepage_push_failed", order_no=order_no, result=result)

    # ─── 查询 ───

    async def get_order(self, order_id: int) -> WorkOrder | None:
        stmt = (
            select(WorkOrder)
            .where(WorkOrder.id == order_id)
            .options(selectinload(WorkOrder.logs))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_order_by_no(self, order_no: str) -> WorkOrder | None:
        stmt = select(WorkOrder).where(WorkOrder.order_no == order_no)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_orders(
        self,
        status: str | None = None,
        order_type: str | None = None,
        creator: str | None = None,
        assignee: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[WorkOrder], int]:
        """列表查询，返回 (orders, total)。"""
        stmt = select(WorkOrder)
        count_stmt = select(func.count(WorkOrder.id))

        if status:
            stmt = stmt.where(WorkOrder.status == status)
            count_stmt = count_stmt.where(WorkOrder.status == status)
        if order_type:
            stmt = stmt.where(WorkOrder.order_type == order_type)
            count_stmt = count_stmt.where(WorkOrder.order_type == order_type)
        if creator:
            stmt = stmt.where(WorkOrder.creator == creator)
            count_stmt = count_stmt.where(WorkOrder.creator == creator)
        if assignee:
            stmt = stmt.where(WorkOrder.assignee == assignee)
            count_stmt = count_stmt.where(WorkOrder.assignee == assignee)

        total = (await self.session.execute(count_stmt)).scalar() or 0
        stmt = stmt.order_by(desc(WorkOrder.created_at)).limit(limit).offset(offset)
        orders = list((await self.session.execute(stmt)).scalars().all())

        return orders, total

    # ─── 统计 ───

    async def get_stats(self) -> dict[str, int]:
        """工单统计。"""
        result = {}
        for status in ["submitted", "pending", "processing", "verifying", "completed", "rejected"]:
            stmt = select(func.count(WorkOrder.id)).where(WorkOrder.status == status)
            result[status] = (await self.session.execute(stmt)).scalar() or 0
        result["total"] = sum(result.values())
        return result

    # ─── 内部 ───

    async def _gen_order_no(self) -> str:
        """生成工单编号 WO-YYYYMMDD-XXXX。"""
        today = datetime.now().strftime("%Y%m%d")
        prefix = f"WO-{today}-"

        stmt = select(func.count(WorkOrder.id)).where(WorkOrder.order_no.startswith(prefix))
        count = (await self.session.execute(stmt)).scalar() or 0
        return f"{prefix}{count + 1:04d}"

    @staticmethod
    def _run_pre_checks(order_type: str, detail: dict[str, Any]) -> dict[str, Any]:
        """执行前置校验（当前为规则模拟，后续接真实 API）。"""
        rules = PRE_CHECK_RULES.get(order_type, [])
        results: dict[str, Any] = {}

        for rule in rules:
            if rule == "check_tpc":
                results["tpc"] = {"passed": True, "message": "TPC 检查通过（待接入真实 API）"}
            elif rule == "check_backup_cleared":
                results["backup"] = {"passed": True, "message": ".backup 已清理（待接入真实 API）"}
            elif rule == "check_module_path":
                module = detail.get("module_path", "")
                valid = module.startswith("[N][腾讯云边缘可用区]") or module.startswith("[腾讯云][边缘计算]")
                results["module_path"] = {
                    "passed": valid or not module,
                    "message": "模块路径正确" if valid else f"模块路径异常: {module}",
                }
            elif rule == "check_target_position":
                results["target_position"] = {"passed": True, "message": "目标机位可用（待接入数全通）"}
            elif rule == "check_sideband":
                results["sideband"] = {"passed": True, "message": "sideband=否（待接入真实检查）"}

        return results

    async def _resolve_assignee(self, order_type: str) -> str:
        """从接口人路由表查询工单类型对应的主负责人。"""
        from app.models.contact import Category, Contact, Responsibility

        # 工单类型 → 搜索关键词
        type_keywords = {
            "ecm_export": "母机重装",
            "host_deploy": "母机重装",
            "migration": "搬迁",
            "repair": "母机故障",
        }
        keyword = type_keywords.get(order_type, "")
        if not keyword:
            return ""

        try:
            from sqlalchemy import select
            from sqlalchemy.orm import selectinload

            stmt = (
                select(Responsibility)
                .join(Category)
                .where(Category.name.ilike(f"%{keyword}%"))
                .where(Responsibility.priority == 1)
                .options(selectinload(Responsibility.contact))
                .limit(1)
            )
            result = await self.session.execute(stmt)
            resp = result.scalar_one_or_none()
            if resp and resp.contact:
                return resp.contact.name
        except Exception:
            pass

        return DEFAULT_ASSIGNEES.get(order_type, "")
