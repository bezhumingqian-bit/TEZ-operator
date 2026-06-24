"""云霄平台 — API 直调客户端（绕开 DOM，直接调 cgi 接口）。

基于诊断抓包（2026-06-24 data/diag_yunxiao/）验证的接口：
- data360/zone          → 全量可用区 + zoneId 映射
- honeycomb/host        → 母机全量结构化数据（分页）

优势：
- 无需展开 accordion、点下拉、翻页、按列下标解析表格
- headless 下 100% 可靠，因为完全是 fetch API 调用
- 数据源是云霄前端自己的数据接口，和页面表格同一份数据
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from app.clients.browser_session import BrowserSession, is_login_url
from app.utils.logger import get_logger

log = get_logger(__name__)

_BASE = "https://yunxiao.vstation.woa.com"
_HOST_PAGE = f"{_BASE}/synergy/honeycomb-host"
_INVENTORY_PAGE = f"{_BASE}/synergy/beacon-instance-sales-config"

# 请求超时（秒）
_PAGE_GOTO_TIMEOUT = 60000
_REQUEST_TIMEOUT = 60000
_LOGIN_WAIT = 120
_POLL_INTERVAL = 3

# 每区最大翻页数
_MAX_PAGES = 50
_PAGE_SIZE = 500


class YunxiaoApiClient:
    """云霄平台 API 直调客户端。

    在已登录的 BrowserSession 上下文中，通过 page.evaluate 发起同源 fetch，
    复用 cookies/SSO 登录态，绕开所有 DOM 交互。
    """

    _log_prefix = "yunxiao_api"

    def __init__(self) -> None:
        self._zone_cache: dict[str, dict] | None = None  # zone_name → {region, regionAlias, zoneId}

    # ── 公共接口（与 YunxiaoBrowserImpl 保持一致）──

    async def query_host_machines(
        self,
        zone: str | None = None,
        zones: list[str] | None = None,
        region: str | None = None,
        machine_type: str | None = None,
        instance_family: str | None = None,
        is_empty_host: bool = False,
    ) -> list[dict]:
        """查询母机管理 — 按 TEZ 可用区获取。

        在单个 page 上下文中完成所有 API 调用（zone 缓存 + 逐区查询），
        避免反复创建 page 的开销。
        """
        target_zones = zones or ([zone] if zone else [])
        if not target_zones:
            log.warning(f"{self._log_prefix}.no_zones")
            return []

        await self._ensure_zone_cache()

        all_results: list[dict] = []

        async with BrowserSession.page() as page:
            await self._ensure_logged_in(page)

            for zone_name in target_zones:
                z_info = self._zone_cache.get(zone_name) if self._zone_cache else None
                if not z_info:
                    log.warning(f"{self._log_prefix}.zone_not_found", zone=zone_name)
                    continue

                zone_rows = await self._fetch_host_for_zone_on_page(
                    page,
                    region=z_info["region"],
                    region_alias=z_info["regionAlias"],
                    zone_id=z_info["zoneId"],
                    zone_name=zone_name,
                    is_empty_host=is_empty_host,
                )
                all_results.extend(zone_rows)
                log.info(f"{self._log_prefix}.zone_done", zone=zone_name, rows=len(zone_rows))

        return all_results

    async def query_host_by_keyword(self, keyword: str) -> list[dict]:
        """按固资号 / IP 精确查单台母机。

        优先用 honeycomb/host 的关键词参数；若 API 不支持，则降级全量抓取后本地匹配。
        当前实现：拉全部 TEZ 边缘区母机后本地匹配。
        """
        keyword = (keyword or "").strip()
        if not keyword:
            return []

        await self._ensure_zone_cache()
        all_results = await self.query_host_machines(
            zones=list(self._zone_cache.keys()) if self._zone_cache else [],
        )

        kw = keyword.upper()
        filtered = [
            r for r in all_results
            if kw in (r.get("asset_id") or "").upper() or kw in (r.get("ip") or "").upper()
        ]
        return filtered

    async def query_inventory(
        self,
        zone: str | None = None,
        zones: list[str] | None = None,
        region: str | None = None,
        instance_family: str | None = None,
        instance_type: str | None = None,
    ) -> list[dict]:
        """查询新机型库存 — 按 TEZ 可用区获取可售卖库存。

        调用 beacon/ceres/zone-instanceType-infos，
        逐区查询各实例类型的库存、阈值、CPU/GPU/内存等。
        """
        target_zones = zones or ([zone] if zone else [])
        if not target_zones:
            log.warning(f"{self._log_prefix}.no_zones_inventory")
            return []

        await self._ensure_zone_cache()

        all_results: list[dict] = []

        async with BrowserSession.page() as page:
            await self._ensure_logged_in(page)

            for zone_name in target_zones:
                z_info = self._zone_cache.get(zone_name) if self._zone_cache else None
                if not z_info:
                    log.warning(f"{self._log_prefix}.inventory_zone_not_found", zone=zone_name)
                    continue

                zone_rows = await self._fetch_inventory_for_zone_on_page(
                    page, z_info, zone_name,
                )
                all_results.extend(zone_rows)
                log.info(f"{self._log_prefix}.inventory_zone_done", zone=zone_name, rows=len(zone_rows))

        return all_results

    # ── 内部：zone 缓存 ──

    async def _ensure_zone_cache(self) -> None:
        """懒加载：从 data360/zone 一次拿全部可用区，筛出边缘区构建 zoneId 映射。"""
        if self._zone_cache is not None:
            return

        async with BrowserSession.page() as page:
            await self._ensure_logged_in(page)
            zone_resp = await self._call_cgi_on_page(page, "data360/zone", {"pageNumber": 1, "pageSize": 500})

        zone_data = zone_resp.get("data", {})
        all_zones: list[dict] = zone_data.get("data", []) if isinstance(zone_data, dict) else []

        edge = [z for z in all_zones if "边缘" in (z.get("zoneName") or "")]

        self._zone_cache = {}
        for z in edge:
            self._zone_cache[z["zoneName"]] = {
                "region": z["region"],
                "regionAlias": z["regionAlias"],
                "zoneId": z["zoneId"],
                "zone": z["zone"],
            }

        log.info(
            f"{self._log_prefix}.zone_cache_ready",
            total_zones=len(all_zones),
            edge_zones=len(self._zone_cache),
        )

    # ── 内部：母机数据获取 ──

    async def _fetch_host_for_zone_on_page(
        self,
        page: Any,
        region: str,
        region_alias: str,
        zone_id: int,
        zone_name: str,
        is_empty_host: bool = False,
    ) -> list[dict]:
        """对单个可用区调 honeycomb/host，分页拿全量。"""
        all_rows: list[dict] = []
        seen: set[str] = set()

        for pg in range(_MAX_PAGES):
            offset = pg * _PAGE_SIZE
            data: dict[str, Any] = {
                "region": region,
                "regionAlias": region_alias,
                "zoneId": [zone_id],
                "instanceFamily": [],
                "type": [],
                "flag": [1] if is_empty_host else [],
                "hypervisor": [],  # 全取（含 kvm + baremetal）
                "pool": [],        # 全取（cdc + supp 都拿）
                "appMask": [],
                "soldPool": [],
                "availableGpu": 0,
                "moduleId": [],
                "includeGpu": True,
                "availableCpu": "",
                "availableMem": "",
                "ignoreTags": [],
                "sort": [],
                "offset": offset,
                "limit": _PAGE_SIZE,
                "includeBlock": True,
            }

            resp = await self._call_cgi_on_page(page, "honeycomb/host", data)
            if resp.get("code") != 200:
                log.warning(f"{self._log_prefix}.api_error", zone=zone_name, code=resp.get("code"))
                break

            hd = resp.get("data", {})
            rows: list[dict] = hd.get("data", []) if isinstance(hd, dict) else []
            total = hd.get("totalCount") if isinstance(hd, dict) else len(rows)

            for r in rows:
                key = r.get("ip") or r.get("asset") or str(r.get("deviceId"))
                if key in seen:
                    continue
                seen.add(key)
                all_rows.append(r)

            if offset + len(rows) >= total:
                break

        log.debug(f"{self._log_prefix}.host_page_done", zone=zone_name, total=len(all_rows))
        return self._parse_host_rows(all_rows, zone_name)

    # ── 解析：API 响应 → 现有 dict 格式（保持下游兼容）──

    def _parse_host_rows(self, raw: list[dict], fallback_zone: str = "") -> list[dict]:
        """将 honeycomb/host API 响应字段映射为现有 dict 结构。

        pool_type 派生逻辑：
        - qcloud_cdc → cdc（客户可购买）
        - qcloud_supp → supp（支撑机，客户不可购买）
        - 其他 → other
        """
        results: list[dict] = []
        for r in raw:
            pool_raw = (r.get("pool") or "").strip()
            pool_type = "other"
            if pool_raw == "qcloud_cdc":
                pool_type = "cdc"
            elif pool_raw in ("qcloud_supp", "qcloud_supp_cdc"):
                pool_type = "supp"

            entry = {
                "asset_id": r.get("asset") or "",
                "ip": r.get("ip"),
                "instance_family": r.get("instanceFamily"),
                "device_type": r.get("type"),
                "zone": r.get("zoneName") or fallback_zone,
                "logical_zone": None,
                "pool": pool_raw,
                "pool_type": pool_type,
                "sale_pool": r.get("soldPool"),
                "module_label": str(r.get("moduleId")) if r.get("moduleId") is not None else None,
                "cpu_available": self._safe_float(r.get("cpuAvailable")),
                "cpu_total": self._safe_float(r.get("cpuTotal")),
                "mem_available": self._safe_float(r.get("memAvailable")),
                "mem_total": self._safe_float(r.get("memTotal")),
                "gpu_available": self._safe_float(r.get("gpuAvailable")),
                "gpu_total": self._safe_float(r.get("gpuTotal")),
                "disk_available": self._safe_float(r.get("diskAvailable")),
                "disk_total": self._safe_float(r.get("diskTotal")),
                "local_disk_available": None,
                "local_disk_total": None,
                "is_empty_host": "是" if r.get("emptyFlag") else "否",
                "is_cdh": "是" if r.get("cdhHostFlag") else "否",
                "exclusive_owner": r.get("exclusiveOwner"),
                "tags": self._format_tags(r.get("tags")),
                "machine_model": r.get("type"),
                "health_score": r.get("healthScore"),
                "online_status": r.get("state"),
                "kernel_version": r.get("kernelVersion"),
                "kernel_version_id": r.get("snHypervisor"),
                "manufacturer_module": r.get("vendorModel"),
                "sale_pool_type": r.get("soldPool"),
                "box_type": None,
                "host_updated_at": self._parse_datetime(r.get("updateTime")),
            }
            results.append(entry)
        return results

    # ── 内部：库存数据获取 ──

    async def _fetch_inventory_for_zone_on_page(
        self, page: Any, z_info: dict, zone_name: str,
    ) -> list[dict]:
        """对单个可用区调 beacon/ceres/zone-instanceType-infos，分页拿全量库存。

        请求参数参考云霄库存页实际发的请求：
        - region: ap-guangzhou 等
        - zoneIds: [zoneId]
        - pool: "" (空=全取所有资源池)
        - chargeType: "" (空=全取所有计费类型)
        - soldOut/forceSoldOut: 0
        """
        region = z_info["region"]
        zone_id = z_info["zoneId"]
        all_rows: list[dict] = []
        page_size = 500

        for pg in range(_MAX_PAGES):
            offset = pg * page_size
            data = {
                "region": region,
                "zoneIds": [zone_id],
                "pool": "",          # 全取所有池
                "chargeType": "",    # 全取所有计费类型
                "soldOut": 0,
                "forceSoldOut": 0,
                "offset": offset,
                "limit": page_size,
            }

            resp = await self._call_cgi_on_page(page, "beacon/ceres/zone-instanceType-infos", data)
            if resp.get("code") != 200:
                log.warning(f"{self._log_prefix}.inventory_api_error",
                           zone=zone_name, code=resp.get("code"))
                break

            hd = resp.get("data", {})
            rows: list[dict] = hd.get("data", []) if isinstance(hd, dict) else []
            total = hd.get("totalCount") if isinstance(hd, dict) else len(rows)

            all_rows.extend(rows)

            if offset + len(rows) >= total:
                break

        log.debug(f"{self._log_prefix}.inventory_page_done", zone=zone_name, total=len(all_rows))
        return self._parse_inventory_rows(all_rows, zone_name)

    def _parse_inventory_rows(self, raw: list[dict], fallback_zone: str = "") -> list[dict]:
        """将 beacon/ceres/zone-instanceType-infos 响应映射为现有 InventoryItem 格式。

        字段映射：
        - instanceType → instance_family(提取族名) + instance_type
        - chargeType: 1=包年包月, 2=按时长 → billing_type
        - soldOutLimit → inventory_threshold
        - safeStockLimit → safety_quota
        - deviceClass → device_type
        """
        results: list[dict] = []
        for r in raw:
            instance_type = r.get("instanceType") or ""
            # 提取实例族名（如 S5.SMALL1 → S5）
            family = instance_type.split(".")[0] if "." in instance_type else instance_type

            charge_type_map = {"1": "包年包月", "2": "按时长", "3": "竞价"}
            billing_type = charge_type_map.get(str(r.get("chargeType")), str(r.get("chargeType") or ""))

            inventory_val = r.get("inventory")
            threshold = r.get("soldOutLimit")
            # 售罄判断：库存 ≤ 售罄阈值
            if inventory_val is not None and threshold is not None and inventory_val <= threshold:
                status = "已售罄" if inventory_val == 0 else "即将售罄"
            else:
                status = "可售卖"

            entry = {
                "zone": fallback_zone or r.get("zone"),
                "instance_family": family,
                "instance_type": instance_type,
                "status": status,
                "pool": r.get("pool"),
                "billing_type": billing_type,
                "inventory": inventory_val,
                "inventory_threshold": threshold,
                "safety_quota": r.get("safeStockLimit"),
                "cpu": r.get("cpu"),
                "gpu": r.get("gpu"),
                "storage_block": r.get("storageBlock"),
                "mem": r.get("mem"),
                "device_type": r.get("deviceClass"),
            }
            results.append(entry)
        return results

    # ── 内部：CGI 调用 ──

    async def _call_cgi_on_page(self, page: Any, action: str, data: dict, method: str = "POST") -> dict:
        """在已有 yunxiao 页面上下文里同源 fetch 内部 CGI 接口。"""
        body = {
            "service": "yunxiao",
            "action": action,
            "data": data,
            "options": {"method": method, "path": action},
        }
        url = f"{_BASE}/cgi?i=yunxiao/{action}"

        js = """
        async ({url, body}) => {
            const resp = await fetch(url, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                credentials: 'include',
                body: JSON.stringify(body),
            });
            const text = await resp.text();
            return {status: resp.status, text};
        }
        """
        result = await page.evaluate(js, {"url": url, "body": body})

        if result["status"] != 200:
            log.warning(
                f"{self._log_prefix}.cgi_http_error",
                action=action, status=result["status"],
                text=result["text"][:200],
            )
            return {"code": result["status"], "data": []}

        try:
            import json
            return json.loads(result["text"])
        except Exception:
            log.warning(f"{self._log_prefix}.cgi_parse_error", action=action, text=result["text"][:200])
            return {"code": -1, "data": []}

    async def _ensure_logged_in(self, page: Any) -> None:
        """保证目标页已登录，必要时等待 SSO 完成。

        新 page 从 about:blank 启动，必须先导航到 yunxiao 页面
        才能做同源 fetch（否则跨域）。
        """
        need_nav = "yunxiao.vstation.woa.com" not in (page.url or "")

        if need_nav or is_login_url(page.url):
            await page.goto(_HOST_PAGE, wait_until="domcontentloaded", timeout=_PAGE_GOTO_TIMEOUT)
            await asyncio.sleep(3)

        if is_login_url(page.url):
            waited = 0
            while is_login_url(page.url) and waited < _LOGIN_WAIT:
                for term in ("iOA 登录", "一键认证", "登录", "确认", "继续"):
                    try:
                        loc = page.get_by_text(term).first
                        if await loc.count() > 0 and await loc.is_visible(timeout=400):
                            await loc.click(timeout=2000)
                            await asyncio.sleep(2)
                            break
                    except Exception:
                        pass
                await asyncio.sleep(_POLL_INTERVAL)
                waited += _POLL_INTERVAL

            if is_login_url(page.url):
                log.warning(f"{self._log_prefix}.login_timeout")
            else:
                log.info(f"{self._log_prefix}.login_ok")
                await asyncio.sleep(2)

        # 登录后确认在 yunxiao 域名上（可能被 SSO 重定向到 passport 然后又跳回）
        if "yunxiao.vstation.woa.com" not in (page.url or ""):
            await page.goto(_HOST_PAGE, wait_until="domcontentloaded", timeout=_PAGE_GOTO_TIMEOUT)
            await asyncio.sleep(2)

    # ── 工具 ──

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _format_tags(tags: list[dict] | None) -> str | None:
        if not tags:
            return None
        return ", ".join(t.get("tag") for t in tags if t.get("tag"))

    @staticmethod
    def _parse_datetime(raw: str | None) -> datetime | None:
        if not raw:
            return None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(raw.strip(), fmt)
            except ValueError:
                continue
        return None

    async def close(self) -> None:
        pass
