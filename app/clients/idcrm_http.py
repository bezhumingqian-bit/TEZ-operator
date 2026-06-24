"""IDCRM HTTP 客户端：在 Playwright 页面上下文中直接调用 REST API。

原理：先打开 IDCRM 页面（确保 session），然后用 page.evaluate(fetch()) 调 API。
不需要操作 UI（点下拉框、翻页等），速度快 10x+。

核心 API（抓包确认 2026-05-29）：
- POST /api/idcbackend/position/query — 查询机位列表
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from app.clients.browser_session import BrowserSession, is_login_url
from app.config import get_settings
from app.utils.logger import get_logger

log = get_logger(__name__)


class IDCRMHttpClient:
    """数全通 HTTP API 客户端。"""

    LOGIN_WAIT_TIMEOUT = 120

    def __init__(self) -> None:
        self._settings = get_settings()
        self._base_url = self._settings.idcrm_base_url.rstrip("/")

    async def _ensure_page(self, page) -> bool:
        """确保页面已登录到 IDCRM。"""
        try:
            await page.goto(
                f"{self._base_url}/db/positions",
                wait_until="domcontentloaded",
                timeout=self._settings.browser_page_timeout_ms,
            )
        except Exception:
            pass
        await asyncio.sleep(3)

        if is_login_url(page.url):
            log.info("idcrm_http.waiting_for_login")
            waited = 0
            while is_login_url(page.url) and waited < self.LOGIN_WAIT_TIMEOUT:
                await asyncio.sleep(3)
                waited += 3
            if is_login_url(page.url):
                return False
            await asyncio.sleep(2)

        return True

    async def _fetch_api(self, page, endpoint: str, body: dict) -> dict:
        """在页面上下文中调用 IDCRM API。"""
        body_json = json.dumps(body, ensure_ascii=False)
        result = await page.evaluate(f"""async () => {{
            const resp = await fetch('{endpoint}', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({body_json})
            }});
            return await resp.json();
        }}""")
        return result

    async def query_positions(
        self,
        page,
        idc_unit_name: str | None = None,
        logic_area_attr: str | None = None,
        page_no: int = 1,
        page_size: int = 100,
    ) -> dict[str, Any]:
        """查询机位列表（单页）。"""
        params: dict[str, Any] = {}
        if idc_unit_name:
            params["idc_unit_name"] = [idc_unit_name]
        if logic_area_attr:
            params["logic_area_attr"] = [logic_area_attr]

        body = {"params": params, "page_no": page_no, "page_size": page_size}

        try:
            data = await self._fetch_api(page, "/api/idcbackend/position/query", body)
            if data.get("code") != 0:
                return {"success": False, "message": data.get("msg", "查询失败")}

            result = data.get("result", {})
            return {
                "success": True,
                "total": result.get("total", 0),
                "data": result.get("data", []),
            }
        except Exception as exc:
            log.error("idcrm_http.query_failed", error=str(exc))
            return {"success": False, "message": str(exc)}

    async def query_positions_by_idc(self, idc: str) -> dict[str, Any]:
        """查询指定机房的所有虚拟化机位（自动翻页）。"""
        async with BrowserSession.page() as page:
            if not await self._ensure_page(page):
                return {"success": False, "message": "IDCRM 登录超时"}

            all_positions = []
            page_no = 1

            while True:
                result = await self.query_positions(
                    page,
                    idc_unit_name=idc,
                    logic_area_attr="通用虚拟化bonding区",
                    page_no=page_no,
                    page_size=100,
                )

                if not result.get("success"):
                    if not all_positions:
                        return result
                    break

                data = result.get("data", [])
                if not data:
                    break

                all_positions.extend(data)
                total = result.get("total", 0)

                if len(all_positions) >= total or len(data) < 100:
                    break
                page_no += 1
                if page_no > 50:
                    break

            return self._summarize_positions(all_positions)

    async def query_all_positions(self) -> dict[str, Any]:
        """查询全部虚拟化机位（不限机房，按机房分组）。"""
        async with BrowserSession.page() as page:
            if not await self._ensure_page(page):
                return {"success": False, "message": "IDCRM 登录超时"}

            all_positions = []
            page_no = 1

            while True:
                result = await self.query_positions(
                    page,
                    logic_area_attr="通用虚拟化bonding区",
                    page_no=page_no,
                    page_size=100,
                )

                if not result.get("success"):
                    if not all_positions:
                        return {"success": False, "message": result.get("message")}
                    break

                data = result.get("data", [])
                if not data:
                    break

                all_positions.extend(data)
                total = result.get("total", 0)
                log.info("idcrm_http.fetching", page=page_no, fetched=len(all_positions), total=total)

                if len(all_positions) >= total or len(data) < 100:
                    break
                page_no += 1
                if page_no > 50:
                    break

            return self._group_by_idc(all_positions)

    def _summarize_positions(self, positions: list[dict]) -> dict[str, Any]:
        """统计机位数据。"""
        free_count = 0
        used_count = 0
        other_count = 0
        all_assets: list[str] = []

        for pos in positions:
            status = str(pos.get("position_status", "") or pos.get("status", ""))
            device_info = str(pos.get("pos_device", "") or pos.get("pre_occupy_asset_id", "") or "")
            if device_info:
                assets = re.findall(r"TYSV[0-9A-Z]{6,}", device_info, re.IGNORECASE)
                all_assets.extend(assets)

            if "空闲" in status:
                free_count += 1
            elif "已用" in status or "在用" in status:
                used_count += 1
            else:
                other_count += 1

        return {
            "success": True,
            "total_positions": len(positions),
            "free_count": free_count,
            "used_count": used_count,
            "other_count": other_count,
            "all_assets": list(set(all_assets)),
        }

    def _group_by_idc(self, positions: list[dict]) -> dict[str, Any]:
        """按机房分组。"""
        from app.data.zone_mapping import ZONE_IDC_MAPPING
        idc_to_zone = {v: k for k, v in ZONE_IDC_MAPPING.items()}

        results_by_idc: dict[str, dict] = {}
        for pos in positions:
            idc_unit = pos.get("idc_unit_name", "")
            if idc_unit not in idc_to_zone:
                continue

            if idc_unit not in results_by_idc:
                results_by_idc[idc_unit] = {
                    "idc": idc_unit,
                    "zone": idc_to_zone[idc_unit],
                    "total_positions": 0,
                    "free_count": 0,
                    "used_count": 0,
                    "all_assets": [],
                }

            entry = results_by_idc[idc_unit]
            entry["total_positions"] += 1

            status = str(pos.get("position_status", "") or pos.get("status", ""))
            if "空闲" in status:
                entry["free_count"] += 1
            elif "已用" in status or "在用" in status:
                entry["used_count"] += 1

            device_info = str(pos.get("pos_device", "") or pos.get("pre_occupy_asset_id", "") or "")
            if device_info:
                assets = re.findall(r"TYSV[0-9A-Z]{6,}", device_info, re.IGNORECASE)
                entry["all_assets"].extend(assets)

        for entry in results_by_idc.values():
            entry["all_assets"] = list(set(entry["all_assets"]))

        return {
            "success": True,
            "total_rows": len(positions),
            "zones_found": len(results_by_idc),
            "results": results_by_idc,
        }
