"""云霄库存页 API 嗅探 — 拿 ground truth。"""
import asyncio, json, os, sys
from pathlib import Path

os.environ["TEZ_BROWSER_HEADLESS"] = "true"
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.clients.browser_session import BrowserSession, is_login_url

_INV_PAGE = "https://yunxiao.vstation.woa.com/synergy/beacon-instance-sales-config"
_BASE = "https://yunxiao.vstation.woa.com"

async def cgi(page, action: str, data: dict) -> dict:
    body = {"service":"yunxiao","action":action,"data":data,"options":{"method":"POST","path":action}}
    url = f"{_BASE}/cgi?i=yunxiao/{action}"
    js = """async ({url,body}) => {const r = await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},credentials:'include',body:JSON.stringify(body)}); return {status:r.status,text:await r.text()};}"""
    res = await page.evaluate(js,{"url":url,"body":body})
    return json.loads(res["text"])

async def main():
    captured = []
    async with BrowserSession.page() as page:
        async def on_response(resp):
            u = resp.url
            if any(e in u for e in (".js",".css",".png",".svg",".woff",".ico")):
                return
            ct = resp.headers.get("content-type","")
            if "json" in ct or "api/" in u.lower() or "cgi" in u.lower():
                try:
                    body = await resp.text()
                    captured.append({"url":u,"method":resp.request.method,"req":(resp.request.post_data or "")[:2000],"res":body[:2000]})
                except: pass
        page.on("response", on_response)

        await page.goto(_INV_PAGE, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(4)
        if is_login_url(page.url):
            print("等待登录..."); waited=0
            while is_login_url(page.url) and waited<90:
                for t in ("iOA 登录","一键认证","登录","确认","继续"):
                    try:
                        loc=page.get_by_text(t).first
                        if await loc.count()>0 and await loc.is_visible(timeout=400):
                            await loc.click(timeout=2000); await asyncio.sleep(2); break
                    except: pass
                await asyncio.sleep(3); waited+=3
            if is_login_url(page.url): print("登录超时"); return
            print("已登录"); await asyncio.sleep(3)

        # 查到可用 cgi
        print("\\n>>> 嗅探中...")
        zresp = await cgi(page, "data360/zone", {"pageNumber":1,"pageSize":500})
        edge = [z for z in zresp.get("data",{}).get("data",[]) if "边缘" in (z.get("zoneName")or"")]
        print(f"边缘区: {len(edge)}")

        # 测试 inventory 接口
        for action in [
            "beacon/instance-sales-config",
            "beacon/instance-sales-config/list",
            "data360/instance-sales-config",
            "honeycomb/instance-sales-config",
        ]:
            try:
                r = await cgi(page, action, {"region":"ap-guangzhou","zoneId":[2100010001],"offset":0,"limit":10})
                print(f"  {action}: code={r.get('code')}, has_data={'data' in r}")
                if r.get("data"):
                    print(f"    sample: {json.dumps(r['data'],ensure_ascii=False)[:300]}")
            except Exception as e:
                print(f"  {action}: ERROR {e}")

        await asyncio.sleep(3)
        await page.screenshot(path=Path(__file__).parent.parent/"data"/"diag_yunxiao"/"inv_sniff.png")

    out = Path(__file__).parent.parent/"data"/"diag_yunxiao"/"inv_capture.json"
    out.write_text(json.dumps(captured, ensure_ascii=False, indent=2))
    print(f"\\n>>> 抓包 {len(captured)} 个接口, 存到 {out}")
    for c in captured:
        u = c['url'].split('?i=yunxiao/')[-1] if '?i=' in c['url'] else c['url'][-80:]
        print(f"  POST {u}")
        if c['req']: print(f"    REQ: {c['req'][:200]}")
        if c['res'] and len(c['res'])>20: print(f"    RES: {c['res'][:250]}")

if __name__=="__main__":
    asyncio.run(main())
