"""测试 CAS 登录页的 IOA 按钮实际行为"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.clients.browser_session import BrowserSession
from app.utils.logger import get_logger, setup_logging

setup_logging(level="INFO")
log = get_logger("cas_test")

async def test():
    async with BrowserSession.page() as page:
        # 打开 TCUM CAS 登录页
        await page.goto("https://cas.tcum.woa.com/cas/login?service=https%3A%2F%2Ftcum.woa.com%2F", 
                        wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)
        
        log.info(f"初始 URL: {page.url[:120]}")
        
        # 列出 CAS 页面的所有可点击元素
        clickable = await page.evaluate("""() => {
            const el = document.querySelectorAll('button, a, input[type="submit"], [class*="btn"]');
            return Array.from(el).map(e => ({
                tag: e.tagName,
                text: (e.innerText || e.value || e.placeholder || '').trim(),
                class: (e.className || '').slice(0, 80),
                id: e.id || '',
                rect: (() => { const r = e.getBoundingClientRect(); return {x:Math.round(r.x), y:Math.round(r.y), w:Math.round(r.width), h:Math.round(r.height)}; })()
            }));
        }""")
        
        log.info("\nCAS 页面可点击元素:")
        for c in clickable:
            if c['text']:
                log.info(f"  {c['tag']} text='{c['text']}' class='{c['class'][:60]}' pos=({c['rect']['x']},{c['rect']['y']}) size=({c['rect']['w']}x{c['rect']['h']})")
        
        # 截图
        await page.screenshot(path="cas_page.png", full_page=True)
        log.info("\n截图: cas_page.png")
        
        # 点击 IOA 登录
        ioa_btn = page.locator('button:has-text("IOA 登录")').first
        if await ioa_btn.count() > 0:
            log.info("\n点击 IOA 登录按钮...")
            
            # 监听新页面/弹窗
            async def handle_popup(popup):
                log.info(f"检测到弹窗: {popup.url}")
            
            page.on("popup", handle_popup)
            
            await ioa_btn.click(timeout=3000)
            
            # 等待 8 秒看变化
            for i in range(8):
                await asyncio.sleep(1)
                log.info(f"  +{i+1}s URL: {page.url[:150]}")
                if "passport" in page.url or "tcum.woa.com" in page.url and "cas" not in page.url:
                    log.info("  页面已跳转!")
                    break
            
            await page.screenshot(path="cas_after_click.png", full_page=True)
            log.info("截图: cas_after_click.png")
    
    await BrowserSession.close()

asyncio.run(test())
