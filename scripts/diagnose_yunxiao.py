"""云霄母机页诊断脚本 —— 拿"地面真相"，终结盲点循环。

目的：
1. 在 headless（生产同款）下复现 母机管理 查询流程；
2. 每步截图 + dump "更多搜索" accordion 的真实 DOM（class/可见性/结构），
   验证 `.tea-accordion__header` 选择器到底匹不匹配；
3. 抓包记录"点查询"时云霄真正调用的数据接口（URL + 请求体 + 响应片段），
   评估是否能直接调 API 绕开 DOM 点击。

使用：
1. 先停掉 uvicorn（释放浏览器 profile）：lsof -ti:8000 | xargs kill 或 scripts/stop.sh
2. 运行：python scripts/diagnose_yunxiao.py
3. 产物：data/diag_yunxiao/*.png 截图 + dom_dump.txt + api_capture.json

注意：脚本强制 headless=true，复现生产环境的真实失败现象。
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

# 强制 headless，复现生产环境（必须在 import config 之前设置）
os.environ["TEZ_BROWSER_HEADLESS"] = "true"

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.clients.browser_session import BrowserSession, is_login_url  # noqa: E402

_HOST_URL = "https://yunxiao.vstation.woa.com/synergy/honeycomb-host"
_OUT_DIR = Path(__file__).parent.parent / "data" / "diag_yunxiao"


async def main() -> None:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    captured: list[dict] = []
    dom_lines: list[str] = []

    def log_dom(msg: str) -> None:
        print(msg)
        dom_lines.append(msg)

    async with BrowserSession.page() as page:
        # ── 抓包：记录所有 JSON / api / cgi 响应 ──
        async def on_response(response):
            url = response.url
            if any(ext in url for ext in (".js", ".css", ".png", ".svg", ".woff", ".ico", ".map", "favicon")):
                return
            try:
                ct = response.headers.get("content-type", "")
                if "json" in ct or "/api" in url.lower() or "cgi" in url.lower() or "trpc" in url.lower():
                    body = ""
                    try:
                        body = await response.text()
                    except Exception:
                        pass
                    req_body = ""
                    try:
                        req_body = response.request.post_data or ""
                    except Exception:
                        pass
                    captured.append({
                        "url": url,
                        "method": response.request.method,
                        "status": response.status,
                        "request_body": req_body[:1500],
                        "response_body": body[:2000],
                    })
            except Exception:
                pass

        page.on("response", on_response)

        # ── Step 0: 打开页面 + 登录 ──
        log_dom(f">>> goto {_HOST_URL}")
        try:
            await page.goto(_HOST_URL, wait_until="domcontentloaded", timeout=60000)
        except Exception as exc:
            log_dom(f"!!! goto warn: {exc}")
        await asyncio.sleep(4)

        if is_login_url(page.url):
            log_dom(f">>> 登录页，等待 SSO/扫码（最多 90s）: {page.url[:80]}")
            waited = 0
            while is_login_url(page.url) and waited < 90:
                # 尝试自动点 iOA 登录
                for term in ("iOA 登录", "一键认证", "登录", "确认", "继续"):
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
                log_dom("!!! 登录超时，终止")
                _flush(dom_lines, captured)
                return
            log_dom(">>> 登录成功")
            await asyncio.sleep(3)

        if "/honeycomb-host" not in page.url:
            try:
                await page.goto(_HOST_URL, wait_until="domcontentloaded", timeout=60000)
                await asyncio.sleep(3)
            except Exception:
                pass

        await page.screenshot(path=str(_OUT_DIR / "01_loaded.png"), full_page=True)
        log_dom(f">>> 已加载，URL={page.url[:80]}")

        # ── Step 1: 诊断 "更多搜索" 区域 ──
        log_dom("\n===== 诊断 '更多搜索' 候选元素 =====")
        candidates_js = """
        () => {
            const out = [];
            const all = document.querySelectorAll('*');
            for (const el of all) {
                const t = (el.textContent || '').trim();
                // 只看直接含"更多搜索"且自身文本短的元素（避免父容器）
                if (t === '更多搜索' || (t.includes('更多搜索') && t.length < 12)) {
                    const r = el.getBoundingClientRect();
                    out.push({
                        tag: el.tagName,
                        cls: el.className && el.className.toString ? el.className.toString() : String(el.className),
                        text: t,
                        visible: r.width > 0 && r.height > 0,
                        x: Math.round(r.x), y: Math.round(r.y),
                        w: Math.round(r.width), h: Math.round(r.height),
                    });
                }
            }
            return out;
        }
        """
        try:
            cands = await page.evaluate(candidates_js)
            log_dom(f"找到 {len(cands)} 个 '更多搜索' 候选：")
            for c in cands:
                log_dom(f"  <{c['tag']}> class='{c['cls']}' vis={c['visible']} "
                        f"box=({c['x']},{c['y']},{c['w']}x{c['h']}) text='{c['text']}'")
        except Exception as exc:
            log_dom(f"!!! 候选枚举失败: {exc}")

        # 当前可见的表单 label（展开前）
        await _dump_labels(page, log_dom, "展开前")

        # ── Step 2: 尝试点击"更多搜索" ──
        log_dom("\n===== 尝试点击 '更多搜索' =====")
        clicked = await _try_expand(page, log_dom)
        await asyncio.sleep(2)
        await page.screenshot(path=str(_OUT_DIR / "02_after_expand.png"), full_page=True)
        log_dom(f">>> 点击尝试结果: {clicked}")

        # 展开后的表单 label
        await _dump_labels(page, log_dom, "展开后")

        # ── Step 3: dump 整个筛选区 HTML（截断）──
        try:
            form_html = await page.evaluate("""
            () => {
                const f = document.querySelector('.tea-form, form, .search-form');
                return f ? f.outerHTML : 'NO_FORM_FOUND';
            }
            """)
            (_OUT_DIR / "filter_form.html").write_text(form_html[:20000], encoding="utf-8")
            log_dom(f"\n>>> 筛选区 HTML 已存 filter_form.html（{len(form_html)} 字符）")
        except Exception as exc:
            log_dom(f"!!! dump form html 失败: {exc}")

    _flush(dom_lines, captured)


async def _try_expand(page, log_dom) -> str:
    """多策略尝试展开'更多搜索'，返回成功的策略名。"""
    selectors = [
        ".tea-accordion__header:has-text('更多搜索')",
        "text=更多搜索",
        ":text('更多搜索')",
        "*:has-text('更多搜索')",
    ]
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            n = await loc.count()
            if n == 0:
                log_dom(f"  [skip] '{sel}' count=0")
                continue
            log_dom(f"  [try] '{sel}' count={n}, 尝试 click")
            await loc.click(timeout=3000)
            return f"click:{sel}"
        except Exception as exc:
            log_dom(f"  [fail] '{sel}': {str(exc)[:80]}")
    return "ALL_FAILED"


async def _dump_labels(page, log_dom, phase: str) -> None:
    try:
        labels = await page.evaluate("""
        () => {
            const out = [];
            const els = document.querySelectorAll('.tea-form__label, .tea-form__item label, label');
            for (const e of els) {
                const r = e.getBoundingClientRect();
                const t = (e.textContent || '').trim();
                if (t) out.push(t + (r.width > 0 ? '' : '[hidden]'));
            }
            return out;
        }
        """)
        log_dom(f">>> [{phase}] 可见表单 label（{len(labels)}）: {labels}")
    except Exception as exc:
        log_dom(f"!!! dump labels 失败 [{phase}]: {exc}")


def _flush(dom_lines: list[str], captured: list[dict]) -> None:
    (_OUT_DIR / "dom_dump.txt").write_text("\n".join(dom_lines), encoding="utf-8")
    (_OUT_DIR / "api_capture.json").write_text(
        json.dumps(captured, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n{'='*60}")
    print(f"✅ 产物已存到 {_OUT_DIR}")
    print(f"   - dom_dump.txt（{len(dom_lines)} 行诊断）")
    print(f"   - api_capture.json（{len(captured)} 个接口）")
    print(f"   - 01_loaded.png / 02_after_expand.png / filter_form.html")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
