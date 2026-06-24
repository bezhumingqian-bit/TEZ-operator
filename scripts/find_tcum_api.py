"""Search TCUM API endpoint that works."""
import os, sys, asyncio, json
os.environ['TEZ_BROWSER_HEADLESS'] = 'true'
sys.path.insert(0, '.')

from app.clients.browser_session import BrowserSession
from app.clients.base_browser import BaseBrowserImpl

async def test():
    async with BrowserSession.page() as page:
        await page.goto('https://tcum.woa.com', wait_until='domcontentloaded', timeout=30000)
        await asyncio.sleep(3)
        sso = BaseBrowserImpl()
        await sso._try_finish_sso_flow(page)
        await asyncio.sleep(5)
        print(f"Logged in: {page.url[:60]}")

        for ep in [
            'https://tcum.woa.com/api/search/search_by_key',
            'https://cmdb.woa.com/api/search/search_by_key',
        ]:
            body = json.dumps({"key": ["TYSV20061T6N"]})
            result = await page.evaluate(f"""async () => {{
                try {{
                    const r = await fetch('{ep}', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        credentials: 'include',
                        body: '{body}'
                    }})
                    const t = await r.text()
                    return {{ok: r.ok, head: t.substring(0, 150)}}
                }} catch(e) {{
                    return {{error: e.message}}
                }}
            }}""")
            print(f"{ep}: ok={result.get('ok')}, {result.get('head', result.get('error','?'))[:100]}")

asyncio.run(test())
