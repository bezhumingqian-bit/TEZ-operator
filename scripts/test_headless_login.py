"""无头模式 auto_iOA_login 测试脚本。

验证：在 headless=true 模式下，访问 TCUM 首页，
自动检测 iOA SSO 登录页并点击"快速登录"按钮完成认证。
"""
import asyncio
import sys
from pathlib import Path

# 确保项目根目录在 path 中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.clients.browser_session import BrowserSession, auto_iOA_login, is_login_url
from app.utils.logger import get_logger, setup_logging

setup_logging(level="DEBUG")
log = get_logger("test_headless_login")


async def test_tcum():
    """测试 TCUM 平台自动登录"""
    settings = get_settings()
    tcum_url = settings.tcum_base_url.rstrip("/")

    log.info("=" * 50)
    log.info("测试 TCUM 无头模式自动 iOA 登录")
    log.info(f"headless={settings.browser_headless}")
    log.info(f"tcum_url={tcum_url}")
    log.info(f"profile_dir={settings.browser_profile_dir}")
    log.info("=" * 50)

    async with BrowserSession.page() as page:
        # 1. 打开 TCUM 首页
        log.info("Step 1: 打开 TCUM 首页...")
        try:
            await page.goto(tcum_url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            log.warning(f"goto 超时（正常，SSO 中转页可能加载慢）: {e}")

        await asyncio.sleep(3)

        current_url = page.url
        log.info(f"当前 URL: {current_url[:120]}")
        log.info(f"是否在登录页: {is_login_url(current_url)}")

        # 2. 如果在登录页，尝试自动 iOA 登录
        if is_login_url(current_url):
            log.info("Step 2: 检测到 SSO 登录页，尝试自动 iOA 登录...")
            ok = await auto_iOA_login(page, deadline=asyncio.get_running_loop().time() + 30, prefix="test")
            if ok:
                log.info("✅ 自动 iOA 登录成功！")
            else:
                log.warning("❌ 自动 iOA 登录超时/失败")
                # 打印页面标题和可见文本帮助排查
                try:
                    title = await page.title()
                    log.info(f"页面标题: {title}")
                    body_text = await page.text_content("body", timeout=3000)
                    log.info(f"页面文本(前500字): {body_text[:500]}")
                except Exception:
                    pass
                return False
        else:
            log.info("✅ 已有有效登录态，无需重新登录")

        # 3. 验证登录态 — 再次 goto TCUM 首页确认不再是登录页
        await asyncio.sleep(2)
        final_url = page.url
        log.info(f"最终 URL: {final_url[:120]}")
        if is_login_url(final_url):
            log.warning("❌ 登录态验证失败，仍在 SSO 页面")
            return False
        else:
            log.info("✅ 登录态验证通过，已在 TCUM 业务页面")
            return True


async def test_cmdb():
    """测试 CMDB 平台自动登录"""
    settings = get_settings()
    cmdb_url = settings.cmdb_base_url.rstrip("/")

    log.info("=" * 50)
    log.info("测试 CMDB 无头模式自动 iOA 登录")
    log.info(f"cmdb_url={cmdb_url}")
    log.info("=" * 50)

    async with BrowserSession.page() as page:
        log.info("Step 1: 打开 CMDB 首页...")
        try:
            await page.goto(cmdb_url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            log.warning(f"goto 超时: {e}")

        await asyncio.sleep(3)

        current_url = page.url
        log.info(f"当前 URL: {current_url[:120]}")
        log.info(f"是否在登录页: {is_login_url(current_url)}")

        if is_login_url(current_url):
            log.info("Step 2: 尝试自动 iOA 登录...")
            ok = await auto_iOA_login(page, deadline=asyncio.get_running_loop().time() + 30, prefix="test_cmdb")
            if ok:
                log.info("✅ CMDB 自动登录成功！")
            else:
                log.warning("❌ CMDB 自动登录失败")
                return False
        else:
            log.info("✅ 已有有效登录态")

        await asyncio.sleep(2)
        if is_login_url(page.url):
            log.warning("❌ CMDB 登录态验证失败")
            return False
        else:
            log.info("✅ CMDB 登录态验证通过")
            return True


async def main():
    results = {}
    
    # 测试 TCUM
    try:
        results["tcum"] = await test_tcum()
    except Exception as e:
        log.error(f"TCUM 测试异常: {e}")
        results["tcum"] = False

    # 测试 CMDB
    try:
        results["cmdb"] = await test_cmdb()
    except Exception as e:
        log.error(f"CMDB 测试异常: {e}")
        results["cmdb"] = False

    # 汇总
    log.info("=" * 50)
    log.info("测试结果汇总:")
    for platform, ok in results.items():
        status = "✅ 通过" if ok else "❌ 失败"
        log.info(f"  {platform}: {status}")

    await BrowserSession.close()
    
    all_ok = all(results.values())
    if all_ok:
        log.info("🎉 全部通过！无头模式自动 iOA 登录可行")
    else:
        log.warning("⚠️  部分失败，需要进一步排查")
    return all_ok


if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
