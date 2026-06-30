"""嗅探 passport.woa.com 页面的按钮"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.clients.browser_session import BrowserSession, auto_iOA_login
from app.utils.logger import get_logger, setup_logging

setup_logging(level="INFO")
log = get_logger("sniff_passport")

async def sniff():
    async with BrowserSession.page() as page:
        # 打开 TCUM（会跳转到 CAS 登录页）
        await page.goto("https://tcum.woa.com", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(5)
        
        log.info(f"TCUM CAS 页面 URL: {page.url[:150]}")
        
        # 点击 IOA 登录
        btn = page.locator('button:has-text("IOA 登录")').first
        if await btn.count() > 0:
            log.info("找到 IOA 登录按钮，点击...")
            await btn.click(timeout=3000)
            # 等待跳转
            await asyncio.sleep(5)
        
        # 现在的页面
        log.info(f"点击后 URL: {page.url[:200]}")
        log.info(f"页面标题: {await page.title()}")
        
        await page.screenshot(path="passport_page.png", full_page=True)
        log.info("截图已保存 passport_page.png")
        
        # 列出所有按钮
        buttons = await page.evaluate("""() => {
            const btns = document.querySelectorAll('button, a, [role="button"], [class*="btn"]');
            return Array.from(btns).map((b, i) => ({
                index: i,
                tag: b.tagName,
                text: (b.innerText || b.value || '').trim().slice(0, 100),
                class: (b.className || '').slice(0, 80),
                id: b.id || '',
                visible: b.offsetParent !== null
            }));
        }""")
        
        log.info(f"\n=== passport 页面按钮 ({len(buttons)} 个) ===")
        for b in buttons:
            if b['text']:
                log.info(f"  [{b['index']}] {b['tag']} text='{b['text']}' class='{b['class']}' visible={b['visible']}")

    await BrowserSession.close()

asyncio.run(sniff())
