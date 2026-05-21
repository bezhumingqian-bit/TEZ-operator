"""导入知识中枢数据到数据库。

从 docs/ 手册和链接清单导入。
用法：python -m scripts.import_knowledge
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models.base import Base
from app.models.knowledge import FAQ, KnowledgeArticle, PlatformLink


# ─── 知识手册数据 ───

ARTICLES = [
    {"title": "TEZ 产品背景", "category": "manual", "summary": "TEZ与ECM/CDC/CDZ关系、网络架构、支持能力", "tags": "TEZ,ECM,产品,架构", "importance": 5, "source_file": "docs/01-tez-product-background.md"},
    {"title": "周边系统集成", "category": "manual", "summary": "CMDB表结构、vstation API、云API 3.0", "tags": "CMDB,API,集成", "importance": 4, "source_file": "docs/02-周边系统集成.md"},
    {"title": "Python开发栈", "category": "manual", "summary": "项目骨架、HTTP/MySQL/签名、任务调度", "tags": "Python,开发,FastAPI", "importance": 3, "source_file": "docs/03-Python开发栈.md"},
    {"title": "FAQ与使用", "category": "manual", "summary": "运营FAQ、调账规则、大客户坑、报价折扣", "tags": "FAQ,运营,调账,报价", "importance": 5, "source_file": "docs/04-FAQ与使用.md"},
    {"title": "接口人与协作", "category": "manual", "summary": "30+接口人清单、场景化找人指南", "tags": "接口人,协作,找人", "importance": 5, "source_file": "docs/05-接口人与协作.md"},
    {"title": "机型与成本", "category": "manual", "summary": "机型成本表、计费标签、规格、适配流程", "tags": "机型,成本,计费", "importance": 4, "source_file": "docs/06-机型与成本.md"},
    {"title": "机房与可用区规划", "category": "manual", "summary": "32个TEZ节点分布、25年资源规划", "tags": "机房,可用区,节点,规划", "importance": 4, "source_file": "docs/07-机房与可用区规划.md"},
    {"title": "资源运营SOP", "category": "sop", "summary": "找机器/投放/搬迁/模块ID速查", "tags": "SOP,找机器,投放,搬迁", "importance": 5, "source_file": "docs/08-资源运营SOP.md"},
    {"title": "交接清单与权限", "category": "manual", "summary": "24个待办、26个系统入口、特殊红线", "tags": "交接,权限,红线", "importance": 4, "source_file": "docs/09-交接清单与权限.md"},
    {"title": "系统总体设计", "category": "manual", "summary": "北极星目标、5大模块、技术架构、4个里程碑", "tags": "设计,架构,路线图", "importance": 5, "source_file": "docs/10-系统总体设计.md"},
]

# ─── 平台链接（脱敏 URL）───

LINKS = [
    {"name": "ECM 运营管理系统", "purpose": "资源看板、机房数据、资源预留、配额策略、账单导出", "url": "#ecm", "importance": 3},
    {"name": "CMDB 服务器查询", "purpose": "按固资号/模块查服务器", "url": "#cmdb", "importance": 3},
    {"name": "TCUM CMDB", "purpose": "按固资号查服务器（机房/模块/IP/状态）", "url": "#tcum", "importance": 3},
    {"name": "数全通-机位列表", "purpose": "机架机位查询（开区交付/搬迁必用）", "url": "#idcrm", "importance": 3},
    {"name": "云霄平台", "purpose": "云霄入口（VS调度、机型配置、库存）", "url": "#yunxiao", "importance": 3},
    {"name": "野鹤系统", "purpose": "白名单管理（可用区+APPID开白）", "url": "#yehe", "importance": 3},
    {"name": "磐石", "purpose": "产品管理（上下架/定价）、客户查询", "url": "#panshi", "importance": 2},
    {"name": "QCC", "purpose": "机型配置、上线", "url": "#qcc", "importance": 2},
    {"name": "QFlow", "purpose": "开区流程", "url": "#qflow", "importance": 2},
    {"name": "地域系统", "purpose": "可用区上线管理", "url": "#region", "importance": 2},
    {"name": "OBS", "purpose": "成本明细", "url": "#obs", "importance": 1},
    {"name": "secmyadmin", "purpose": "CMDB母机查询导出", "url": "#secmyadmin", "importance": 2},
    {"name": "安灯工具", "purpose": "库存可视化", "url": "#andon", "importance": 1},
    {"name": "njecm", "purpose": "母机剩余资源、可用装箱", "url": "#njecm", "importance": 2},
]

# ─── FAQ ───

FAQS = [
    {"question": "TEZ 有哪些机型比较充足？", "answer": "<b>25G：</b>S5（Y0-MI32-25G / CG3-25G / Y0-MI52-25G）<br><b>10G：</b>S5nt（CG3-10G）<br>不充足的是 IT5C 和裸金属系列", "category": "机型"},
    {"question": "报价怎么报？", "answer": "九部单独报价，其他人报刊例价。低价底价2折起，具体按客户体量沟通。", "category": "报价"},
    {"question": "搬迁前需要注意什么？", "answer": "1. 搬迁裸金属时需确认目标机位 sideband 属性为\"否\"<br>2. 提单修改属性需要1天<br>3. 投放前要清 .backup<br>4. 确认TPC<br>5. 确认模块路径", "category": "搬迁"},
    {"question": "S5nt 和 ECM S4 的区别？", "answer": "TEZ的S5nt肯定是CG3-10G生产，而ECM的S4有三种母机（CG1/CG2/CG3）都可以。从ECM的CG1/CG2搬过来无法生产S5nt。", "category": "机型"},
    {"question": "什么情况下要主动扩容？", "answer": "看商机，预留20台备机。空闲机位不够时提前拉起机位扩容评估流程（SLA 1.5个月）。", "category": "扩容"},
    {"question": "调账有哪些客户需要做？", "answer": "多个大客户需要月度调账（ECM导出对齐+手工调整），具体清单见运营SOP。", "category": "调账"},
    {"question": "ECM→TEZ 迁移怎么做？", "answer": "1. 资源运营OnePage新增记录<br>2. 通知搬迁接口人走流程<br>3. 在群里通知模块转移到 [N][腾讯云边缘可用区]-[公有云]-[TEZ]-[线下资源][待上线]", "category": "迁移"},
]


async def main() -> None:
    settings = get_settings()
    db_url = settings.database_url
    if "sqlite+pysqlite" in db_url:
        db_url = db_url.replace("sqlite+pysqlite", "sqlite+aiosqlite")
    elif "sqlite" in db_url and "aiosqlite" not in db_url:
        db_url = db_url.replace("sqlite://", "sqlite+aiosqlite://")
    elif "pymysql" in db_url:
        db_url = db_url.replace("pymysql", "aiomysql")

    engine = create_async_engine(db_url, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as session:
        # 导入文章
        for data in ARTICLES:
            session.add(KnowledgeArticle(**data))
        await session.flush()
        print(f"✅ 导入 {len(ARTICLES)} 篇知识文章")

        # 导入链接
        for data in LINKS:
            session.add(PlatformLink(**data))
        await session.flush()
        print(f"✅ 导入 {len(LINKS)} 个平台链接")

        # 导入FAQ
        for i, data in enumerate(FAQS):
            session.add(FAQ(**data, sort_order=i))
        await session.flush()
        print(f"✅ 导入 {len(FAQS)} 条FAQ")

        await session.commit()
        print("\n🎉 知识中枢数据导入完成！")


if __name__ == "__main__":
    asyncio.run(main())
