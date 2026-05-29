"""抓包脚本：自动捕获 TCUM 和 IDCRM 的 API 请求。

使用方式：
1. 先停掉 uvicorn（释放浏览器 profile）
2. 运行：python scripts/sniff_apis.py
3. 脚本会打开浏览器，执行查询操作，记录所有 API 请求
4. 结果保存到 scripts/api_sniff_result.json
"""

import asyncio
import json
from pathlib import Path

# 添加项目路径
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.clients.browser_session import BrowserSession, is_login_url


async def sniff_platform(name: str, url: str, search_action=None):
    """打开平台页面并捕获所有 API 请求。"""
    captured = []

    async with BrowserSession.page() as page:
        # 监听所有网络请求和响应
        async def on_response(response):
            req_url = response.url
            # 排除静态资源
            if any(ext in req_url for ext in ['.js', '.css', '.png', '.jpg', '.svg', '.woff', '.ico', '.map']):
                return
            # 排除 favicon 等
            if 'favicon' in req_url or 'analytics' in req_url or 'telemetry' in req_url:
                return

            try:
                content_type = response.headers.get('content-type', '')
                if 'json' in content_type or 'api' in req_url.lower() or 'cgi' in req_url.lower():
                    body = ''
                    try:
                        body = await response.text()
                    except:
                        pass

                    # 获取请求体
                    req_body = ''
                    try:
                        req_body = response.request.post_data or ''
                    except:
                        pass

                    captured.append({
                        'url': req_url,
                        'method': response.request.method,
                        'status': response.status,
                        'request_headers': dict(response.request.headers) if response.request.headers else {},
                        'request_body': req_body[:500] if req_body else '',
                        'response_body': body[:1000] if body else '',
                        'content_type': content_type,
                    })
            except Exception as e:
                captured.append({'url': req_url, 'error': str(e)})

        page.on('response', on_response)

        # 打开页面
        print(f'\n{"="*60}')
        print(f'>>> 正在打开 {name}: {url}')
        try:
            await page.goto(url, wait_until='networkidle', timeout=30000)
        except:
            pass
        await asyncio.sleep(5)

        current_url = page.url
        print(f'>>> 当前 URL: {current_url[:80]}')

        if is_login_url(current_url):
            print('>>> ⚠️ 需要登录！等待30秒让你扫码...')
            waited = 0
            while is_login_url(page.url) and waited < 60:
                await asyncio.sleep(3)
                waited += 3
            if is_login_url(page.url):
                print('>>> ❌ 登录超时')
                return captured
            print('>>> ✅ 登录成功，继续...')
            await asyncio.sleep(3)

        # 执行搜索操作
        if search_action:
            await search_action(page)
            await asyncio.sleep(5)

        print(f'>>> 共捕获 {len(captured)} 个 API 请求')

    return captured


async def tcum_search(page):
    """TCUM 搜索操作。"""
    print('>>> 执行 TCUM 搜索...')
    try:
        # 找到搜索框并输入固资号
        inputs = page.locator('input')
        count = await inputs.count()
        for i in range(count):
            placeholder = await inputs.nth(i).get_attribute('placeholder') or ''
            if '搜索' in placeholder or '固资' in placeholder or '资产' in placeholder:
                await inputs.nth(i).fill('TYSV_TEST_ASSET')
                await inputs.nth(i).press('Enter')
                print('>>> 已输入搜索词并回车')
                return
        # 如果没找到特定的，试第一个可见输入框
        for i in range(min(count, 5)):
            if await inputs.nth(i).is_visible():
                await inputs.nth(i).fill('TYSV_TEST_ASSET')
                await inputs.nth(i).press('Enter')
                print('>>> 已在第一个输入框搜索')
                return
    except Exception as e:
        print(f'>>> 搜索失败: {e}')


async def idcrm_search(page):
    """IDCRM 查询操作。"""
    print('>>> 执行 IDCRM 查询...')
    try:
        # 点击查询按钮
        btn = page.get_by_text('查 询')
        if await btn.count() > 0:
            await btn.first.click()
            print('>>> 已点击查询按钮')
    except Exception as e:
        print(f'>>> 查询失败: {e}')


async def main():
    print('='*60)
    print('API 抓包工具 - TEZ Operator')
    print('='*60)

    all_results = {}

    # 1. TCUM
    tcum_results = await sniff_platform(
        'TCUM',
        'https://tcum.example.com',  # 实际运行时替换为真实地址
        search_action=tcum_search,
    )
    all_results['tcum'] = tcum_results

    # 关闭浏览器让下一个重新启动
    await BrowserSession.close()

    # 2. IDCRM
    from app.config import get_settings
    settings = get_settings()
    idcrm_url = settings.idcrm_base_url.rstrip('/') + '/db/positions'

    idcrm_results = await sniff_platform(
        'IDCRM(数全通)',
        idcrm_url,
        search_action=idcrm_search,
    )
    all_results['idcrm'] = idcrm_results

    await BrowserSession.close()

    # 保存结果
    output_path = Path(__file__).parent / 'api_sniff_result.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    print(f'\n{"="*60}')
    print(f'✅ 结果已保存到: {output_path}')
    print(f'   TCUM: {len(tcum_results)} 个请求')
    print(f'   IDCRM: {len(idcrm_results)} 个请求')
    print(f'{"="*60}')

    # 打印关键发现
    for platform, results in all_results.items():
        print(f'\n--- {platform.upper()} 关键 API ---')
        for r in results:
            if r.get('method') == 'POST' or ('api' in r.get('url', '').lower()):
                print(f'  {r.get("method")} {r.get("url", "")[:100]}')
                if r.get('request_body'):
                    print(f'    Body: {r["request_body"][:80]}')


if __name__ == '__main__':
    asyncio.run(main())
