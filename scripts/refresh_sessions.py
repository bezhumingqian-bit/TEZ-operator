"""每日自动刷新 CMDB/TCUM/IDCRM 浏览器登录态。

CMDB/IDCRM：直接访问首页，cookie 持久化
TCUM：通过 IOA 登录按钮一键认证（headless 可用）
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))


async def _try_refresh(name: str, url: str, headless: bool = True) -> bool:
    from playwright.async_api import async_playwright

    profile_dir = Path("data/playwright-profile").resolve()
    print(f"[{datetime.now():%H:%M:%S}] {name}: {url}")

    try:
        pw = await async_playwright().start()
        # 启用新 headless 模式以复用 SAML 登录态
        args = ["--disable-blink-features=AutomationControlled"]
        if headless:
            args.append("--headless=new")
        ctx = await pw.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=headless,
            viewport={"width": 1440, "height": 900},
            args=args,
        )
        try:
            page = await ctx.new_page()
            await page.goto(url, timeout=30000, wait_until="domcontentloaded")
            await asyncio.sleep(2)
            title = await page.title()

            # TCUM: 点 IOA 登录按钮（有时需手机确认，最长等 2 分钟）
            if name == "TCUM" and ("登录" in title):
                ioa_btn = page.locator("text=IOA 登录")
                if await ioa_btn.count() > 0:
                    print(f"  🔑 点击 IOA 登录（可能需要手机确认，最长等 120s）...")
                    await ioa_btn.first.click()
                    for i in range(60):
                        await asyncio.sleep(2)
                        title = await page.title()
                        if title and "登录" not in title:
                            break
                        if i % 10 == 0 and i > 0:
                            print(f"    已等 {i*2}s，当前页: {title[:40]}")
                    else:
                        print(f"  ❌ {name}: 超时 120s，请手动确认")
                        return False
                else:
                    print(f"  ❌ {name}: 无 IOA 按钮")
                    return False

            if "登录" in title:
                print(f"  ❌ {name}: 需登录 (title={title[:30]})")
                return False
            print(f"  ✅ {name}: {title[:50]}")
            return True
        finally:
            await ctx.close()
            await pw.stop()
    except Exception as e:
        print(f"  ❌ {name}: {e!s}")
        return False


_PLATFORMS = [
    ("TCUM", "https://tcum.woa.com"),
    ("CMDB", "https://cmdb.woa.com"),
    ("IDCRM", "https://idcrm.woa.com/db/positions"),
]


async def main() -> None:
    print(f"=== Session 续期 [{datetime.now():%Y-%m-%d %H:%M}] ===")

    for attempt in range(3):
        if attempt > 0:
            print(f"\n🔄 第 {attempt + 1} 轮重试（等 5s）...")
            await asyncio.sleep(5)

        ok = fail = 0
        failed: list[str] = []
        for name, url in _PLATFORMS:
            if await _try_refresh(name, url):
                ok += 1
            else:
                fail += 1
                failed.append(name)
            await asyncio.sleep(1)

        if fail == 0:
            print(f"\n✅ 全部成功 ({ok} OK)")
            return

    print(f"\n⚠️ 最终: {ok} OK / {fail} FAIL ({failed})")
    sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
