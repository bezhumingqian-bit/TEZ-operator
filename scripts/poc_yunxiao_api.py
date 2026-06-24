"""云霄 API 直调 PoC —— 验证绕开 DOM、直接调 cgi 接口可行性。

不改任何生产代码，纯验证：
1. data360/zone 拿全部可用区，过滤带"边缘"的 TEZ 区，按 region 分组
2. 对某个边缘 region+zoneId，调 honeycomb/host 拿结构化母机数据

使用：先停 uvicorn，再 python scripts/poc_yunxiao_api.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

os.environ["TEZ_BROWSER_HEADLESS"] = "true"
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.clients.browser_session import BrowserSession, is_login_url  # noqa: E402

_BASE = "https://yunxiao.vstation.woa.com"
_HOST_PAGE = f"{_BASE}/synergy/honeycomb-host"


async def _cgi(page, action: str, data: dict, method: str = "POST") -> dict:
    """在已登录页面上下文里同源调用 cgi 接口。"""
    body = {
        "service": "yunxiao",
        "action": action,
        "data": data,
        "options": {"method": method, "path": action},
    }
    js = """
    async ({url, body}) => {
        const resp = await fetch(url, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            credentials: 'include',
            body: JSON.stringify(body),
        });
        const text = await resp.text();
        return {status: resp.status, text};
    }
    """
    url = f"{_BASE}/cgi?i=yunxiao/{action}"
    res = await page.evaluate(js, {"url": url, "body": body})
    if res["status"] != 200:
        return {"_http": res["status"], "_text": res["text"][:300]}
    try:
        return json.loads(res["text"])
    except Exception:
        return {"_parse_error": res["text"][:300]}


async def main() -> None:
    async with BrowserSession.page() as page:
        await page.goto(_HOST_PAGE, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(4)
        if is_login_url(page.url):
            print(">>> 等待登录（90s）...")
            waited = 0
            while is_login_url(page.url) and waited < 90:
                for term in ("iOA 登录", "一键认证", "登录", "确认"):
                    try:
                        loc = page.get_by_text(term).first
                        if await loc.count() > 0 and await loc.is_visible(timeout=400):
                            await loc.click(timeout=2000)
                            await asyncio.sleep(2)
                            break
                    except Exception:
                        pass
                await asyncio.sleep(3)
                waited += 3
            if is_login_url(page.url):
                print("!!! 登录超时")
                return
        print(f">>> 已登录: {page.url[:70]}")

        # ── 1. 拿全部可用区，过滤边缘区 ──
        zone_resp = await _cgi(page, "data360/zone", {"pageNumber": 1, "pageSize": 500})
        zones = zone_resp.get("data", {}).get("data", []) if isinstance(zone_resp.get("data"), dict) else []
        print(f"\n>>> data360/zone 返回 {len(zones)} 个可用区")
        edge = [z for z in zones if "边缘" in (z.get("zoneName") or "")]
        print(f">>> 其中带'边缘'的 TEZ 可用区 {len(edge)} 个：")
        by_region: dict[str, list] = {}
        for z in edge:
            by_region.setdefault(z.get("regionName") or z.get("region"), []).append(
                f"{z.get('zoneName')}(id={z.get('zoneId')},region={z.get('region')})"
            )
        for rname, items in by_region.items():
            print(f"   [{rname}] {len(items)} 个: {items}")

        if not edge:
            print("!!! 没有边缘可用区，dump 前 5 个 zone 看结构")
            print(json.dumps(zones[:5], ensure_ascii=False, indent=2))
            return

        # ── 2. 对第一个边缘区调 honeycomb/host ──
        sample = edge[0]
        region = sample.get("region")
        region_alias = sample.get("regionAlias")
        zone_id = sample.get("zoneId")
        print(f"\n>>> 测试 honeycomb/host: region={region} zoneId={zone_id} ({sample.get('zoneName')})")
        host_resp = await _cgi(page, "honeycomb/host", {
            "region": region,
            "regionAlias": region_alias,
            "zoneId": [zone_id],
            "instanceFamily": [], "type": [], "flag": [],
            "hypervisor": [], "pool": [], "appMask": [], "soldPool": [],
            "availableGpu": 0, "moduleId": [], "includeGpu": True,
            "availableCpu": "", "availableMem": "", "ignoreTags": [],
            "sort": [], "offset": 0, "limit": 20, "includeBlock": True,
        })
        hd = host_resp.get("data", {})
        rows = hd.get("data", []) if isinstance(hd, dict) else []
        total = hd.get("totalCount") if isinstance(hd, dict) else None
        print(f">>> honeycomb/host 返回 code={host_resp.get('code')} totalCount={total} 本页={len(rows)}")
        if rows:
            r0 = rows[0]
            keys = ["asset", "ip", "type", "zoneId", "region", "pool", "emptyFlag",
                    "cpuAvailable", "cpuTotal", "memAvailable", "memTotal", "state", "healthScore"]
            print(">>> 样例首行关键字段：")
            for k in keys:
                print(f"     {k} = {r0.get(k)}")
        else:
            print(">>> 该区无母机（可能正常），完整响应片段：")
            print(json.dumps(host_resp, ensure_ascii=False)[:500])

        # 存全量产物供分析
        out = Path(__file__).parent.parent / "data" / "diag_yunxiao" / "poc_result.json"
        out.write_text(json.dumps({
            "edge_zones_by_region": by_region,
            "sample_host_total": total,
            "sample_host_first_row": rows[0] if rows else None,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n✅ PoC 产物存到 {out}")


if __name__ == "__main__":
    asyncio.run(main())
