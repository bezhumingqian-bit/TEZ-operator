"""Test TCUM browser automation in headless mode."""
import os, sys, asyncio, json
os.environ['TEZ_BROWSER_HEADLESS'] = 'true'
sys.path.insert(0, '.')

async def test():
    from app.clients.tcum_browser import TCUMBrowserImpl
    tcum = TCUMBrowserImpl()
    devices = await tcum.batch_search(['TYSV20061T6N', 'TYSV20061T65'])
    print(f'Found {len(devices)} devices')
    for d in devices:
        print(json.dumps(d, ensure_ascii=False)[:200])
    await tcum.close()

asyncio.run(test())
