"""三源融合真实验证脚本。

用法：
    # 固资号查询
    python -m scripts.test_fusion_real --query TYSVXXXXX

    # IP 查询
    python -m scripts.test_fusion_real --query 10.0.0.1

    # 仅测某一源（调试用）
    python -m scripts.test_fusion_real --query TYSVXXXXX --source tcum

环境要求：
    - .env 中 TEZ_CMDB_BASE_URL / TEZ_TCUM_BASE_URL / TEZ_IDCRM_BASE_URL 已配真实地址
    - data/playwright-profile 中登录态有效（7 天内扫过码）
    - 工位机网络能访问三个内网系统

脚本会自动把客户端模式设为 browser，无需改 .env。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

# 把项目根加到 path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 强制 browser 模式
os.environ.setdefault("TEZ_CMDB_MODE", "browser")
os.environ.setdefault("TEZ_TCUM_MODE", "browser")
os.environ.setdefault("TEZ_IDCRM_MODE", "browser")
os.environ.setdefault("TEZ_BROWSER_HEADLESS", "false")


def _banner(msg: str) -> None:
    print(f"\n{'═' * 60}")
    print(f"  {msg}")
    print(f"{'═' * 60}")


async def test_single_source(source: str, query: str, qtype: str) -> dict | None:
    """单独测试某个源。"""

    from app.config import get_settings

    s = get_settings()

    if source == "tcum":
        from app.clients.tcum_browser import TCUMBrowserImpl

        impl = TCUMBrowserImpl()
        if qtype == "asset_id":
            return await impl.get_by_asset(query)
        else:
            return await impl.search_by_ip(query)

    elif source == "cmdb":
        from app.clients.cmdb_browser import CMDBBrowserImpl

        impl = CMDBBrowserImpl()
        if qtype == "asset_id":
            return await impl.get_by_asset(query)
        else:
            return await impl.get_by_ip(query)

    elif source == "idcrm":
        from app.clients.idcrm_browser import IDCRMBrowserImpl

        impl = IDCRMBrowserImpl()
        # IDCRM 需要 idc 参数，单独测不了完整流程
        print("  [IDCRM] 单独测试需要 idc 参数，跳过（融合流程中由 TCUM 提供）")
        return None

    return None


async def test_fusion(query: str, qtype: str) -> None:
    """完整三源融合测试。"""

    from app.services.host_service import HostService

    service = HostService()

    _banner(f"融合查询: {query} (类型: {qtype})")
    t0 = time.time()

    try:
        if qtype == "asset_id":
            result = await service.get_host(query)
        else:
            result = await service.get_host_by_ip(query)
    except Exception as exc:
        print(f"\n  ❌ 融合查询异常: {type(exc).__name__}: {exc}")
        return
    finally:
        elapsed = time.time() - t0
        print(f"\n  ⏱ 耗时: {elapsed:.2f}s")

    if result is None:
        print("\n  ⚠️  未找到结果（三源均无数据）")
        return

    print("\n  ✅ 融合结果：")
    # 打印主要字段
    fields = [
        ("固资号", result.asset_id),
        ("IP", result.ip),
        ("Zone", result.zone),
        ("机型", result.machine_type),
        ("状态", result.status),
        ("IDC/机房", result.idc),
        ("机柜", result.cabinet),
        ("机位", result.position),
        ("业务模块", result.module),
        ("客户", result.customer),
        ("AppID", result.app_id),
        ("TPC", result.has_tpc),
        ("负责人", result.owner),
        ("备份负责人", result.backup_owners),
        ("城市", result.city),
        ("机器类型", result.server_type),
        ("使用年限", result.use_years),
    ]
    for name, val in fields:
        if val is not None and val != [] and val != {}:
            print(f"     {name:12s} │ {val}")

    # 元信息
    meta = result.meta
    print(f"\n  📊 数据源: {meta.data_sources}")
    print(f"  📊 是否部分: {meta.partial}")
    if meta.errors:
        print(f"  ⚠️  错误: {meta.errors}")
    print(f"  📊 同步时间: {meta.last_sync_at}")

    # raw_json 原始数据（可选展示）
    if result.raw_json:
        print("\n  📦 各源原始数据概要：")
        for src, data in result.raw_json.items():
            if data:
                keys = list(data.keys()) if isinstance(data, dict) else "non-dict"
                print(f"     {src:8s} │ 字段数={len(data) if isinstance(data, dict) else '?'}, keys={keys[:8]}...")
            else:
                print(f"     {src:8s} │ (无数据)")


async def main() -> None:
    parser = argparse.ArgumentParser(description="三源融合真实验证")
    parser.add_argument("--query", "-q", required=True, help="固资号或 IP 地址")
    parser.add_argument(
        "--source",
        "-s",
        choices=["tcum", "cmdb", "idcrm", "all"],
        default="all",
        help="仅测单源（默认 all = 完整融合）",
    )
    args = parser.parse_args()

    query = args.query.strip()

    # 自动判断类型
    import re
    if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", query):
        qtype = "ip"
    else:
        qtype = "asset_id"

    print(f"🔍 查询: {query}")
    print(f"📋 类型: {qtype}")
    print(f"🎯 源: {args.source}")

    if args.source == "all":
        await test_fusion(query, qtype)
    else:
        _banner(f"单源测试: {args.source}")
        t0 = time.time()
        try:
            result = await test_single_source(args.source, query, qtype)
        except Exception as exc:
            print(f"\n  ❌ {args.source} 异常: {type(exc).__name__}: {exc}")
            return
        elapsed = time.time() - t0
        print(f"\n  ⏱ 耗时: {elapsed:.2f}s")
        if result:
            print(f"\n  ✅ {args.source} 返回数据：")
            print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        else:
            print(f"\n  ⚠️  {args.source} 无结果")


if __name__ == "__main__":
    asyncio.run(main())
