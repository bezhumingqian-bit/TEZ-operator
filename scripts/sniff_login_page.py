"""嗅探 passport.woa.com 登录页面的按钮和元素"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.clients.browser_session import BrowserSession
from app.utils.logger import get_logger, setup_logging

setup_logging(level="DEBUG")
log = get_logger("sniff_login")

async def sniff():
    settings = get_settings()
    
    async with BrowserSession.page() as page:
        # 打开 TCUM（会跳转到 SSO）
        await page.goto("https://tcum.woa.com", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(5)
        
        url = page.url
        log.info(f"当前 URL: {url}")
        log.info(f"页面标题: {await page.title()}")
        
        # 列出页面上所有按钮
        buttons = await page.evaluate("""() => {
            const btns = document.querySelectorAll('button, a, input[type="submit"], input[type="button"], .btn, [role="button"], [class*="login"], [class*="Login"]');
            return Array.from(btns).map((b, i) => ({
                index: i,
                tag: b.tagName,
                text: (b.innerText || b.value || '').trim().slice(0, 100),
                class: (b.className || '').slice(0, 80),
                id: b.id || '',
                visible: b.offsetParent !== null,
                href: b.href || ''
            }));
        }""")
        
        log.info(f"\n=== 页面按钮列表 ({len(buttons)} 个) ===")
        for b in buttons:
            if b['text'] or b['id']:
                log.info(f"  [{b['index']}] {b['tag']} id={b['id']} class={b['class']} text='{b['text']}' visible={b['visible']}")

        # 也列出所有链接
        links = await page.evaluate("""() => {
            const all = document.querySelectorAll('a');
            return Array.from(all).map((a, i) => ({
                index: i,
                text: (a.innerText || '').trim().slice(0, 100),
                href: (a.href || '').slice(0, 150),
                class: (a.className || '').slice(0, 60)
            }));
        }""")
        
        log.info(f"\n=== 页面链接列表 ({len(links)} 个) ===")
        for l in links:
            if l['text']:
                log.info(f"  [{l['index']}] a text='{l['text']}' href='{l['href']}' class='{l['class']}'")
        
        # 截个图
        await page.screenshot(path="login_page.png", full_page=True)
        log.info("\n截图已保存到 login_page.png")

    await BrowserSession.close()

asyncio.run(sniff())
