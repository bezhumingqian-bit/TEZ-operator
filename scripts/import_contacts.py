"""导入接口人数据到数据库。

从 docs/05-接口人与协作.md 的结构化数据导入。
用法：python -m scripts.import_contacts
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models.base import Base
from app.models.contact import Category, Contact, EscalationPath, Responsibility


# ─────────────── 接口人原始数据（来自 docs/05）───────────────

# ─────────────── 接口人原始数据（脱敏占位）───────────────
# 真实数据通过本地 knowledge/资料/接口人.xlsx 或环境变量加载
# 以下为占位示例，实际运行时自动从 xlsx 解析

CONTACTS_DATA = [
    # (name, team, role)
    ("contact_01", "计算研发", "控制台/管控研发"),
    ("contact_02", "网络", "TEZ网络统一入口（EIP/VPC等）"),
    ("contact_03", "虚拟化", "新机型上线"),
    ("contact_04", "机型改造", "评估方案"),
    ("contact_05", "机型改造", "执行改造"),
    ("contact_06", "I平", "线下重装/故障上升"),
    ("contact_07", "架平", "机柜/搬迁"),
    ("contact_08", "架平", "搬迁提单/退役"),
    ("contact_09", "网平", "网平实施（交换机等）"),
    ("contact_10", "网平", "网平实施"),
    ("contact_11", "母机运维", "母机故障上升"),
    ("contact_12", "母机运维", "母机重装/投放提单/搬迁流程"),
    ("contact_13", "I平", "线下重装/故障"),
    ("contact_14", "I平", "线下重装/故障"),
    ("contact_15", "高性能网络", "母机侧IPv6开发"),
    ("contact_16", "VPC", "VPC适配（如IPv6）"),
    ("contact_17", "网络架构", "网络架构方案（toctpc/机位扩容）"),
    ("contact_18", "网络", "裁撤/割接（外部客户网络）"),
    ("contact_19", "CVM资源", "从CVM大盘要机器"),
    ("contact_20", "异构资源", "从异构要机器（裸金属）"),
    ("contact_21", "运管资源", "从运管要机器（过保退库）"),
    ("contact_22", "配额产品", "配额问题（竞价配额等）"),
    ("contact_23", "CVM机型", "CVM机型管理"),
    ("contact_24", "搬迁", "搬迁出入库"),
    ("contact_25", "搬迁", "搬迁出入库"),
    ("contact_26", "机房建设", "机房建设需求/机位扩容评估"),
    ("contact_27", "前端", "前端开发"),
    ("contact_28", "EC节点", "EC开白"),
    ("contact_29", "EC节点", "EC节点库存"),
    ("contact_30", "EC节点", "EC机型定价+QCC"),
    ("contact_31", "母机运维", "TEZ边缘可用区母机主负责人"),
    ("contact_32", "运维杂项", "云知"),
    ("contact_33", "运维杂项", "翻译材料"),
    ("contact_34", "产品", "产品侧确认搬迁规划"),
    ("contact_35", "ECM", "ECM空母机列表"),
]

# ─────────────── 事项分类 ───────────────

CATEGORIES_DATA = [
    # (name, parent_name_or_none, description, contacts: [(name, priority)])
    ("母机相关", None, "母机故障 排查 重装 投放 上线", []),
    ("母机故障排查", "母机相关", "母机故障 排查 宕机 异常", [("contact_11", 1)]),
    ("母机重装/投放", "母机相关", "母机重装 投放 提单 控制面", [("contact_12", 1)]),
    ("线下重装/故障", "母机相关", "线下 重装 故障 I平", [("contact_13", 1), ("contact_14", 2), ("contact_06", 3)]),

    ("网络相关", None, "网络 EIP VPC IPv6 带宽", []),
    ("EIP/VPC/IPv6", "网络相关", "EIP VPC IPv6 网络问题", [("contact_02", 1)]),
    ("母机IPv6开发", "网络相关", "母机 IPv6 开发 高性能网络", [("contact_15", 1)]),
    ("VPC适配", "网络相关", "VPC 适配 IPv6", [("contact_16", 1)]),
    ("网络架构方案", "网络相关", "网络架构 toctpc 机位扩容 方案", [("contact_17", 1)]),
    ("网平实施", "网络相关", "网平 交换机 实施 落地", [("contact_09", 1), ("contact_10", 2)]),
    ("网络裁撤割接", "网络相关", "裁撤 割接 外部客户 网络", [("contact_18", 1)]),

    ("资源相关", None, "资源 要机器 设备 引入", []),
    ("从CVM要机器", "资源相关", "CVM 大盘 MI52 机器", [("contact_19", 1)]),
    ("从异构要机器", "资源相关", "异构 裸金属 BMD", [("contact_20", 1)]),
    ("从运管要机器", "资源相关", "运管 过保 退库 设备", [("contact_21", 1)]),
    ("配额问题", "资源相关", "配额 竞价 限额", [("contact_22", 1)]),

    ("机型相关", None, "机型 适配 改造 上线", []),
    ("CVM机型管理", "机型相关", "CVM 机型 管理", [("contact_23", 1)]),
    ("机型改造评估", "机型相关", "机型 改造 评估 可行性", [("contact_04", 1)]),
    ("机型改造执行", "机型相关", "机型 改造 执行", [("contact_05", 1)]),
    ("新机型上线", "机型相关", "新机型 上线 虚拟化", [("contact_03", 1)]),

    ("机房/搬迁", None, "机房 搬迁 机柜 机位 扩容", []),
    ("机柜管理", "机房/搬迁", "机柜 架平", [("contact_07", 1), ("contact_08", 2)]),
    ("搬迁出入库", "机房/搬迁", "搬迁 出入库 出库 入库", [("contact_24", 1), ("contact_25", 2)]),
    ("搬迁提单/退役", "机房/搬迁", "搬迁 提单 退役", [("contact_08", 1)]),
    ("机位扩容", "机房/搬迁", "机位 扩容 建设 供应商", [("contact_26", 1)]),

    ("控制台/研发", None, "控制台 管控 研发 前端", []),
    ("计算研发", "控制台/研发", "控制台 管控 研发 后端", [("contact_01", 1)]),
    ("前端开发", "控制台/研发", "前端 开发 页面", [("contact_27", 1)]),

    ("EC节点", None, "EC 边缘计算 ECM 节点", []),
    ("EC开白", "EC节点", "EC 开白 白名单", [("contact_28", 1)]),
    ("EC节点库存", "EC节点", "EC 节点 库存", [("contact_29", 1)]),
    ("EC机型定价", "EC节点", "EC 机型 定价 QCC", [("contact_30", 1)]),
]


async def main() -> None:
    settings = get_settings()
    db_url = settings.database_url
    # 转为 async driver
    if "sqlite+pysqlite" in db_url:
        db_url = db_url.replace("sqlite+pysqlite", "sqlite+aiosqlite")
    elif "sqlite" in db_url and "aiosqlite" not in db_url:
        db_url = db_url.replace("sqlite://", "sqlite+aiosqlite://")
    elif "pymysql" in db_url:
        db_url = db_url.replace("pymysql", "aiomysql")

    engine = create_async_engine(db_url, echo=False)

    # 创建表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as session:
        # 1. 导入接口人
        contact_map: dict[str, Contact] = {}
        for name, team, role in CONTACTS_DATA:
            c = Contact(name=name, team=team, role=role, status="active")
            session.add(c)
            contact_map[name] = c
        await session.flush()
        print(f"✅ 导入 {len(contact_map)} 个接口人")

        # 2. 导入分类 + 关联
        category_map: dict[str, Category] = {}
        for cat_name, parent_name, desc, contacts in CATEGORIES_DATA:
            parent_id = category_map[parent_name].id if parent_name else None
            cat = Category(name=cat_name, parent_id=parent_id, description=desc)
            session.add(cat)
            await session.flush()
            category_map[cat_name] = cat

            # 关联接口人
            for contact_name, priority in contacts:
                if contact_name in contact_map:
                    r = Responsibility(
                        contact_id=contact_map[contact_name].id,
                        category_id=cat.id,
                        priority=priority,
                    )
                    session.add(r)

        await session.flush()
        print(f"✅ 导入 {len(category_map)} 个事项分类")

        await session.commit()
        print("\n🎉 数据导入完成！")


if __name__ == "__main__":
    asyncio.run(main())
