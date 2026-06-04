# "等待登录 + 可取消" 方案设计文档

## 📋 概述

本文档详细描述如何在"节点资源概况"查询功能中实现**等待用户 SSO 登录完成**，并允许用户**随时取消等待**的完整方案。

---

## 🎯 需求分析

### 当前问题

```
时间线：
T+0    用户首次访问系统 → 浏览器弹 SSO 登录窗口
T+500  前端加载完毕
T+1000 用户开始扫码登录（浏览器中）
T+1500 ❌ 用户在前端点击"查询资源概况" → API 立即返回空结果（SSO 还没完成）
T+5000 用户手机扫码完成 → cookies 文件被保存
T+5500 用户刷新页面后重新查询 → 才能看到正确的数据
```

### 目标状态

```
T+0    用户首次访问系统 → 浏览器弹 SSO 登录窗口
T+1500 用户在前端点击"查询资源概况"
       → 前端显示"检测到首次登录，等待 SSO 完成..."
       → ✅ 前端以 5 秒间隔轮询 /api/v1/zones/{zone}/overview/status
       → 后端等待登录态有效（或超时）
       
T+2000 SSO 完成 → cookies 文件被保存
       → 后端检测到登录有效 → 启动采集
       → 返回进度信息
       
T+2500 数据采集中...
       → 前端显示"正在从 IDCRM/TCUM 采集数据（1/2）"
       
T+4000 采集完成
       → 返回完整数据
       → 前端切换到展示模式
```

---

## 🏗️ 架构设计

### 1. 前后端通信模型

```
前端状态机:
┌─────────────┐
│   idle      │ (初始状态)
└─────┬───────┘
      │ 用户点击"查询"
      ↓
┌─────────────────────────┐
│ waiting_for_login       │ (等待用户完成 SSO)
│ - 显示"请在浏览器中登录"  │
│ - 5秒轮询一次            │
│ - 用户可按 ESC 取消      │
└─────┬───────────────────┘
      │ 若超时 (300s)
      ├→ ❌ timeout_error
      │ 若用户按 ESC
      ├→ ❌ cancelled
      │ 若 SSO 完成
      ↓
┌─────────────────────────┐
│ syncing_from_cloud      │ (采集数据中)
│ - 显示进度条              │
│ - 用户可按 ESC 取消      │
└─────┬───────────────────┘
      │ 采集失败
      ├→ ❌ sync_error
      │ 用户取消
      ├→ ❌ cancelled
      │ 采集成功
      ↓
┌─────────────┐
│  success    │ (展示数据)
└─────────────┘
```

### 2. API 状态流转

#### 端点 1: GET /api/v1/zones/{zone}/overview

**职责**：获取数据（本地缓存或触发同步）

```
缓存有效 → 直接返回数据 (10ms)
       ↓
缓存无效或过期
       ↓
检查登录态
       ├─ 无效 & profile 不存在 (首次使用)
       │  ↓ 返回 status: "waiting_for_login"
       │  ↓ 前端需轮询 /api/v1/zones/{zone}/overview/status
       │
       ├─ 无效 & profile 存在但过期 (7+ 天)
       │  ↓ 返回 status: "login_expired"
       │  ↓ 前端需轮询 /api/v1/zones/{zone}/overview/status
       │
       └─ 有效
          ↓ 直接同步数据
          ↓ 返回 status: "success"
```

#### 端点 2: GET /api/v1/zones/{zone}/overview/status

**职责**：查询数据采集的进度和状态

返回示例：

```json
{
  "zone": "zone_a",
  "status": "waiting_for_login",
  "message": "等待用户完成 SSO 登录...",
  "progress": null,
  "request_id": "req-uuid-xxx",
  "elapsed_seconds": 3.2,
  "timeout_seconds": 300
}
```

```json
{
  "zone": "zone_a", 
  "status": "syncing",
  "message": "正在从 IDCRM 采集虚拟化机位数据",
  "progress": { "step": 1, "total": 2, "percent": 50 },
  "request_id": "req-uuid-xxx",
  "elapsed_seconds": 12.5,
  "data_partial": { "free_count": 10, "all_assets": [] }
}
```

#### 端点 3: POST /api/v1/zones/{zone}/overview/cancel

**职责**：取消正在进行的采集

```json
{
  "zone": "zone_a",
  "request_id": "req-uuid-xxx"
}
```

---

## 💻 代码实现

### 后端实现

#### 1. 新增数据结构：采集任务管理

```python
# app/services/zone_sync_manager.py

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from app.utils.logger import get_logger

log = get_logger(__name__)


class SyncStatus(str, Enum):
    """采集任务状态"""
    IDLE = "idle"                          # 空闲
    WAITING_FOR_LOGIN = "waiting_for_login"  # 等待登录
    SYNCING = "syncing"                    # 采集中
    SUCCESS = "success"                    # 成功
    CANCELLED = "cancelled"                # 已取消
    TIMEOUT = "timeout"                    # 超时
    ERROR = "error"                        # 错误


@dataclass
class SyncTask:
    """采集任务"""
    zone: str
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: SyncStatus = SyncStatus.IDLE
    message: str = ""
    progress: Optional[dict[str, Any]] = None
    data: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    
    # 取消信号
    cancel_requested: bool = False
    
    @property
    def elapsed_seconds(self) -> float:
        """已耗时（秒）"""
        start = self.started_at or self.created_at
        end = self.ended_at or datetime.now()
        return (end - start).total_seconds()
    
    def to_dict(self) -> dict[str, Any]:
        """转为 API 响应"""
        return {
            "zone": self.zone,
            "request_id": self.request_id,
            "status": self.status.value,
            "message": self.message,
            "progress": self.progress,
            "data": self.data,
            "error": self.error,
            "elapsed_seconds": self.elapsed_seconds,
        }


class ZoneSyncManager:
    """采集任务管理器"""
    
    def __init__(self):
        # zone → 最新的 SyncTask
        self._tasks: dict[str, SyncTask] = {}
        self._lock = asyncio.Lock()
    
    async def create_task(self, zone: str) -> SyncTask:
        """创建一个新的采集任务"""
        async with self._lock:
            task = SyncTask(zone=zone, status=SyncStatus.IDLE)
            self._tasks[zone] = task
            log.info("sync_task.created", zone=zone, request_id=task.request_id)
            return task
    
    async def get_task(self, zone: str) -> Optional[SyncTask]:
        """获取当前任务"""
        async with self._lock:
            return self._tasks.get(zone)
    
    async def update_task(
        self,
        zone: str,
        status: Optional[SyncStatus] = None,
        message: Optional[str] = None,
        progress: Optional[dict] = None,
        data: Optional[dict] = None,
        error: Optional[str] = None,
    ) -> SyncTask:
        """更新任务状态"""
        async with self._lock:
            task = self._tasks.get(zone)
            if not task:
                raise ValueError(f"Task not found for zone {zone}")
            
            if status is not None:
                task.status = status
                if task.started_at is None:
                    task.started_at = datetime.now()
            if message is not None:
                task.message = message
            if progress is not None:
                task.progress = progress
            if data is not None:
                task.data = data
            if error is not None:
                task.error = error
            if status in (SyncStatus.SUCCESS, SyncStatus.CANCELLED, SyncStatus.TIMEOUT, SyncStatus.ERROR):
                task.ended_at = datetime.now()
            
            log.info(
                "sync_task.updated",
                zone=zone,
                request_id=task.request_id,
                status=task.status.value,
            )
            return task
    
    async def cancel_task(self, zone: str) -> bool:
        """标记任务为取消"""
        async with self._lock:
            task = self._tasks.get(zone)
            if task and task.status in (SyncStatus.WAITING_FOR_LOGIN, SyncStatus.SYNCING):
                task.cancel_requested = True
                log.info("sync_task.cancel_requested", zone=zone)
                return True
        return False
    
    async def clear_task(self, zone: str) -> None:
        """清空已完成的任务"""
        async with self._lock:
            if zone in self._tasks:
                del self._tasks[zone]


# 全局单例
_manager: Optional[ZoneSyncManager] = None


def get_sync_manager() -> ZoneSyncManager:
    global _manager
    if _manager is None:
        _manager = ZoneSyncManager()
    return _manager
```

#### 2. 修改 BrowserSession 添加等待登录方法

```python
# app/clients/browser_session.py (新增方法)

import time


class BrowserSession:
    """全局单例 BrowserContext。"""
    
    # ... 现有代码 ...
    
    @staticmethod
    def wait_for_login_valid(timeout_sec: int = 300) -> bool:
        """阻塞等待登录态有效。
        
        Args:
            timeout_sec: 最长等待时间（秒）
            
        Returns:
            True 表示登录态有效，False 表示超时
        """
        s = get_settings()
        profile_dir = Path(s.browser_profile_dir)
        cookies_file = profile_dir / "Default" / "Cookies"
        
        start = time.time()
        check_interval = 2  # 每 2 秒检查一次
        
        log.info(
            "browser.wait_for_login_start",
            timeout_sec=timeout_sec,
            cookies_file=str(cookies_file),
        )
        
        while time.time() - start < timeout_sec:
            if cookies_file.exists():
                # 检查 mtime 是否在有效期内
                try:
                    mtime = cookies_file.stat().st_mtime
                    age_days = (time.time() - mtime) / 86400
                    if age_days < s.browser_login_valid_days:
                        log.info("browser.wait_for_login_success", age_days=age_days)
                        return True
                except OSError:
                    pass
            
            time.sleep(check_interval)
        
        log.warning("browser.wait_for_login_timeout", elapsed=time.time() - start)
        return False
    
    @staticmethod
    def clear_profile() -> None:
        """清除浏览器 profile（用于测试或重新登录）"""
        s = get_settings()
        profile_dir = Path(s.browser_profile_dir)
        if profile_dir.exists():
            import shutil
            try:
                shutil.rmtree(profile_dir)
                log.info("browser.profile_cleared", path=str(profile_dir))
            except Exception as exc:
                log.error("browser.profile_clear_failed", error=str(exc))
```

#### 3. 修改 ZoneResourceService 支持任务管理

```python
# app/services/zone_resource_service.py (修改现有代码)

async def get_zone_overview(
    self, zone: str, force_refresh: bool = False
) -> dict[str, Any]:
    """获取可用区资源概况。
    
    新逻辑：
    - 如果登录态无效 → 返回等待状态
    - 前端轮询 status 端点
    - 登录完成后，重新调用此方法继续采集
    """
    from app.clients.browser_session import BrowserSession
    
    # 1. 读本地数据库
    snapshot = await self._get_snapshot(zone)
    
    if snapshot and not force_refresh:
        # 检查是否过期
        if snapshot.last_sync_at and (datetime.now() - snapshot.last_sync_at) < timedelta(days=SYNC_EXPIRE_DAYS):
            # 未过期，直接返回本地数据
            devices = await self._get_devices(zone)
            return self._build_response(snapshot, devices, from_cache=True)
    
    # 2. 需要同步 → 检查登录态
    if not BrowserSession.profile_exists():
        # 首次使用，profile 不存在
        return {
            "zone": zone,
            "status": "login_required",
            "message": (
                "系统首次启动，需要进行身份验证。请在浏览器窗口中使用 SSO（iOA、企业微信等）完成登录。"
                "通常需要 1-5 分钟。登录完成后，本系统会自动采集数据。"
            ),
            "next_action": "请稍候，系统会自动重试数据采集",
            "retry_after_seconds": 60,
            "free_count": None,
            "online_devices": [],
            "offline_devices": [],
        }
    
    if not BrowserSession.is_login_valid():
        # Profile 存在但登录态无效或过期
        return {
            "zone": zone,
            "status": "login_expired",
            "message": "登录态已过期（超过 7 天），请重新扫码登录。",
            "next_action": "请在浏览器窗口中点击登录",
            "retry_after_seconds": 60,
            "free_count": None,
            "online_devices": [],
            "offline_devices": [],
        }
    
    # 3. 登录态有效 → 同步
    log.info("zone_resource.sync_start", zone=zone, force=force_refresh)
    result = await self._sync_from_cloud(zone)
    
    if result:
        return result
    
    # 4. 同步失败但有旧数据，仍然返回旧数据
    if snapshot:
        devices = await self._get_devices(zone)
        resp = self._build_response(snapshot, devices, from_cache=True)
        resp["sync_warning"] = "同步失败，显示的是上次缓存数据"
        return resp
    
    return {"zone": zone, "message": "暂无数据，且同步失败"}


async def _sync_from_cloud(self, zone: str) -> dict[str, Any] | None:
    """从 IDCRM + TCUM 拉取最新数据并写入本地库。
    
    与原有逻辑相同，但新增支持：
    - 任务进度更新
    - 取消检查
    """
    from app.config import get_settings
    from app.data.zone_mapping import ZONE_IDC_MAPPING
    from app.services.zone_sync_manager import get_sync_manager
    
    manager = get_sync_manager()
    task = await manager.create_task(zone)
    
    try:
        idc = ZONE_IDC_MAPPING.get(zone)
        if not idc:
            return {"zone": zone, "message": "未知可用区"}
        
        settings = get_settings()
        if settings.idcrm_mode != "browser":
            return {"zone": zone, "message": "需要 browser 模式才能同步"}
        
        # 检查是否被取消
        task = await manager.get_task(zone)
        if task and task.cancel_requested:
            await manager.update_task(zone, status=SyncStatus.CANCELLED, message="用户取消了采集")
            return None
        
        # Step 1: IDCRM 查全量机位
        from app.skills.idcrm_position_skill import IDCRMPositionSkill
        
        await manager.update_task(
            zone,
            status=SyncStatus.SYNCING,
            message="正在从 IDCRM 采集虚拟化机位数据",
            progress={"step": 1, "total": 2, "percent": 0},
        )
        
        skill = IDCRMPositionSkill()
        pos_result = await skill.query_free_positions(idc)
        
        # 检查取消
        task = await manager.get_task(zone)
        if task and task.cancel_requested:
            await manager.update_task(zone, status=SyncStatus.CANCELLED, message="用户取消了采集")
            return None
        
        await manager.update_task(
            zone,
            progress={"step": 1, "total": 2, "percent": 50},
            data={"positions": pos_result},
        )
        
        if pos_result.get("idc_not_found"):
            await self._save_snapshot(zone, idc, pos_result, [], [], [], 0)
            result = await manager.update_task(
                zone,
                status=SyncStatus.SUCCESS,
                message=pos_result.get("message", "该可用区尚未开区"),
            )
            return {"zone": zone, "idc": idc, "idc_not_found": True, "message": result.message}
        
        all_assets = pos_result.get("all_assets", [])
        
        # Step 2: TCUM 批量查
        online_devices: list[dict] = []
        offline_devices: list[dict] = []
        non_tez_devices: list[dict] = []
        
        if all_assets and settings.tcum_mode == "browser":
            # 检查取消
            task = await manager.get_task(zone)
            if task and task.cancel_requested:
                await manager.update_task(zone, status=SyncStatus.CANCELLED, message="用户取消了采集")
                return None
            
            await manager.update_task(
                zone,
                message="正在从 TCUM 采集设备状态数据",
                progress={"step": 2, "total": 2, "percent": 50},
            )
            
            from app.clients.tcum_browser import TCUMBrowserImpl
            
            tcum = TCUMBrowserImpl()
            devices = await tcum.batch_search(all_assets[:100])
            
            # ... 分类逻辑（与原有相同）...
            TEZ_KEYWORDS = ["腾讯云边缘可用区", "TEZ"]
            
            for dev in devices:
                module = dev.get("module", "") or ""
                status = dev.get("status", "") or ""
                is_tez = any(kw in module for kw in TEZ_KEYWORDS)
                
                if not is_tez:
                    non_tez_devices.append(dev)
                elif status == "online":
                    online_devices.append(dev)
                else:
                    reason = "未知"
                    if "待上线" in module:
                        reason = "模块状态：待上线"
                    elif "上线中" in module:
                        reason = "模块状态：上线中"
                    dev["reason"] = reason
                    offline_devices.append(dev)
        
        # Step 3: 写入本地数据库
        await self._save_snapshot(
            zone, idc, pos_result,
            online_devices, offline_devices, non_tez_devices,
            len(all_assets),
        )
        
        # 返回结果
        snapshot = await self._get_snapshot(zone)
        all_devs = await self._get_devices(zone)
        response = self._build_response(snapshot, all_devs, from_cache=False)
        
        await manager.update_task(
            zone,
            status=SyncStatus.SUCCESS,
            message="数据采集完成",
            progress={"step": 2, "total": 2, "percent": 100},
            data=response,
        )
        
        return response
    
    except Exception as exc:
        log.error("zone_resource.sync_error", zone=zone, error=str(exc))
        await manager.update_task(zone, status=SyncStatus.ERROR, error=str(exc))
        return None
```

#### 4. 新增 API 路由

```python
# app/routers/hosts.py (新增)

from fastapi import Query, BackgroundTasks

@zone_router.get(
    "/{zone}/overview/status",
    summary="查询节点资源概况采集状态",
)
async def get_zone_overview_status(
    zone: str,
    request_id: str = Query(None, description="请求 ID（用于取消操作）"),
) -> dict[str, Any]:
    """实时查询数据采集的状态和进度。
    
    用途：前端轮询此端点了解采集进度，而不需要阻塞等待。
    """
    from app.services.zone_sync_manager import get_sync_manager
    
    manager = get_sync_manager()
    task = await manager.get_task(zone)
    
    if not task:
        return {
            "zone": zone,
            "status": "idle",
            "message": "未发现活跃的采集任务",
            "request_id": request_id,
        }
    
    result = task.to_dict()
    result["timeout_seconds"] = 300
    return result


@zone_router.post(
    "/{zone}/overview/cancel",
    summary="取消正在进行的数据采集",
)
async def cancel_zone_overview_sync(
    zone: str,
    payload: dict = None,
) -> dict[str, Any]:
    """立即取消正在进行的采集任务。"""
    from app.services.zone_sync_manager import get_sync_manager
    
    manager = get_sync_manager()
    cancelled = await manager.cancel_task(zone)
    
    return {
        "zone": zone,
        "cancelled": cancelled,
        "message": "采集任务已标记为取消，将在当前步骤完成后停止" if cancelled else "未发现进行中的任务",
    }
```

---

### 前端实现

#### 1. Vue 3 Composition API 实现

```typescript
// web/src/composables/useZoneOverview.ts

import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'

export type SyncStatus = 
  | 'idle'
  | 'waiting_for_login'
  | 'syncing'
  | 'success'
  | 'cancelled'
  | 'timeout'
  | 'error'

export interface SyncProgress {
  step: number
  total: number
  percent: number
}

export interface SyncTask {
  zone: string
  request_id: string
  status: SyncStatus
  message: string
  progress: SyncProgress | null
  data: Record<string, any> | null
  error: string | null
  elapsed_seconds: number
  timeout_seconds?: number
}

export interface NodeOverviewData {
  zone: string
  idc: string | null
  free_count: number | null
  total_positions: number | null
  total_assets: number
  
  online_devices: Array<{ asset_id: string; ip: string; machine_type: string; module?: string }>
  online_count: number
  
  offline_devices: Array<{ asset_id: string; ip: string; machine_type: string; module?: string; reason: string }>
  offline_count: number
  
  non_tez_count: number
  from_cache: boolean
  last_sync_at: string | null
  message: string
}

export function useZoneOverview() {
  const zone = ref('')
  const loading = ref(false)
  const syncing = ref(false)
  const data = ref<NodeOverviewData | null>(null)
  const error = ref<string | null>(null)
  
  // 采集任务相关
  const task = reactive<SyncTask | null>(null)
  const pollInterval = ref<number | null>(null)
  const pollCount = ref(0)
  
  /**
   * 轮询采集状态
   */
  async function pollStatus() {
    if (!task?.request_id || !zone.value) return
    
    try {
      const response = await fetch(
        `/api/v1/zones/${encodeURIComponent(zone.value)}/overview/status?request_id=${task.request_id}`
      )
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      
      const result: SyncTask = await response.json()
      Object.assign(task, result)
      
      // 根据状态判断是否继续轮询
      if (result.status === 'success') {
        syncing.value = false
        data.value = result.data as NodeOverviewData
        ElMessage.success('数据采集完成')
        stopPolling()
      } else if (result.status === 'timeout' || result.status === 'error' || result.status === 'cancelled') {
        syncing.value = false
        error.value = result.error || result.message
        ElMessage.error(`采集${result.status === 'timeout' ? '超时' : '失败'}：${result.message}`)
        stopPolling()
      }
      // 其他状态（waiting_for_login, syncing）继续轮询
    } catch (e) {
      console.error('轮询失败:', e)
    }
  }
  
  /**
   * 启动轮询
   */
  function startPolling() {
    if (pollInterval.value) return
    pollCount.value = 0
    pollInterval.value = window.setInterval(() => {
      pollCount.value++
      pollStatus()
    }, 5000) // 每 5 秒轮询一次
  }
  
  /**
   * 停止轮询
   */
  function stopPolling() {
    if (pollInterval.value) {
      clearInterval(pollInterval.value)
      pollInterval.value = null
      pollCount.value = 0
    }
  }
  
  /**
   * 取消采集
   */
  async function cancelSync() {
    if (!zone.value) return
    try {
      await fetch(`/api/v1/zones/${encodeURIComponent(zone.value)}/overview/cancel`, {
        method: 'POST',
      })
      ElMessage.info('已请求取消采集')
      stopPolling()
      syncing.value = false
    } catch (e) {
      ElMessage.error('取消失败')
    }
  }
  
  /**
   * 查询数据
   */
  async function fetchOverview(forceRefresh = false) {
    if (!zone.value) {
      ElMessage.warning('请先选择可用区')
      return
    }
    
    loading.value = true
    error.value = null
    syncing.value = false
    
    try {
      const url = `/api/v1/zones/${encodeURIComponent(zone.value)}/overview${forceRefresh ? '?force_refresh=true' : ''}`
      const response = await fetch(url)
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      
      const result = await response.json()
      
      // 判断是否需要等待登录
      if (result.status === 'login_required' || result.status === 'login_expired') {
        syncing.value = true
        task.zone = zone.value
        task.request_id = result.request_id || `${zone.value}-${Date.now()}`
        task.status = result.status
        task.message = result.message
        task.progress = null
        task.data = null
        
        ElMessage.warning(result.message)
        startPolling()
        return
      }
      
      // 正常返回数据
      data.value = result
      if (!result.from_cache) {
        ElMessage.success('数据已从云端刷新')
      }
    } catch (e) {
      error.value = (e as Error).message
      ElMessage.error(`查询失败: ${error.value}`)
    } finally {
      loading.value = false
    }
  }
  
  // 页面卸载时停止轮询
  onUnmounted(() => {
    stopPolling()
  })
  
  return {
    zone,
    loading,
    syncing,
    data,
    error,
    task,
    pollCount,
    fetchOverview,
    cancelSync,
    stopPolling,
  }
}
```

#### 2. Vue 3 组件修改

```vue
<!-- web/src/views/HostSearch.vue (修改节点资源概况 Tab) -->

<template>
  <!-- ... 其他 tab ... -->
  
  <el-tab-pane label="节点资源概况" name="node_overview">
    <div class="host-search__bar">
      <el-select
        v-model="nodeZoneSelected"
        filterable
        size="large"
        placeholder="选择可用区"
        style="width: 360px"
      >
        <el-option v-for="z in zoneOptions" :key="z" :label="z" :value="z" />
      </el-select>
      <el-button
        type="primary"
        size="large"
        :loading="nodeLoading"
        :disabled="!nodeZoneSelected"
        @click="onNodeOverview"
      >
        查询资源概况
      </el-button>
      <el-button
        size="large"
        :loading="nodeRefreshing"
        :disabled="!nodeZoneSelected"
        @click="onNodeForceRefresh"
      >
        🔄 强制刷新
      </el-button>
    </div>

    <div class="host-search__result">
      <!-- 等待登录状态 -->
      <template v-if="syncTask.status === 'waiting_for_login'">
        <el-card shadow="never">
          <el-alert
            type="warning"
            show-icon
            :closable="false"
            title="等待 SSO 登录完成"
            :description="syncTask.message"
          />
          <div style="margin-top: 16px; text-align: center">
            <el-progress :percentage="0" :indeterminate="true" />
            <p style="margin-top: 12px; color: #606266">
              已等待 {{ pollCount * 5 }} 秒 / 最多等待 300 秒
              <el-button text size="small" @click="cancelSync">取消</el-button>
            </p>
          </div>
        </el-card>
      </template>

      <!-- 采集中状态 -->
      <template v-else-if="syncTask.status === 'syncing'">
        <el-card shadow="never">
          <el-alert
            type="info"
            show-icon
            :closable="false"
            :title="syncTask.message"
            description="请稍候，采集可能需要 30 秒..."
          />
          <div style="margin-top: 16px">
            <el-progress 
              v-if="syncTask.progress"
              :percentage="syncTask.progress.percent || 0"
              :format="(p) => `步骤 ${syncTask.progress.step}/${syncTask.progress.total} (${p}%)`"
            />
            <p style="margin-top: 12px; text-align: right">
              <el-button text size="small" @click="cancelSync">取消采集</el-button>
            </p>
          </div>
        </el-card>
      </template>

      <!-- 采集失败 / 超时 -->
      <template v-else-if="syncTask.status === 'timeout' || syncTask.status === 'error' || syncTask.status === 'cancelled'">
        <el-result
          :icon="syncTask.status === 'cancelled' ? 'info' : 'warning'"
          :title="`采集${syncTask.status === 'timeout' ? '超时' : syncTask.status === 'cancelled' ? '已取消' : '失败'}`"
          :sub-title="syncTask.message || syncTask.error"
        >
          <template #extra>
            <el-button type="primary" @click="onNodeOverview">重试</el-button>
          </template>
        </el-result>
      </template>

      <!-- 成功返回数据 -->
      <el-skeleton v-else-if="nodeLoading || nodeRefreshing" :rows="6" animated />
      <template v-else-if="nodeOverviewData">
        <!-- 数据来源提示 -->
        <el-alert
          v-if="nodeOverviewData.from_cache"
          :title="`本地缓存数据（上次同步: ${nodeOverviewData.last_sync_at || '未知'}）`"
          type="info"
          show-icon
          :closable="false"
          style="margin-bottom: 12px"
        />

        <!-- 空闲机位 -->
        <el-card shadow="never" class="node-section">
          <template #header><b>空闲虚拟化机位</b></template>
          <el-alert
            :title="nodeOverviewData.message"
            :type="nodeOverviewData.free_count === null ? 'warning' : (nodeOverviewData.free_count > 0 ? 'success' : 'error')"
            show-icon
            :closable="false"
          />
          <div v-if="nodeOverviewData.idc" class="node-info">
            机房：{{ nodeOverviewData.idc }}
          </div>
        </el-card>

        <!-- 已上线设备 -->
        <el-card v-if="nodeOverviewData.online_devices && nodeOverviewData.online_devices.length" shadow="never" class="node-section" style="margin-top: 16px">
          <template #header>
            <b>已上线设备</b>
            <el-tag size="small" type="success" style="margin-left: 8px">
              {{ nodeOverviewData.online_devices.length }} 台
            </el-tag>
          </template>
          <el-table :data="nodeOverviewData.online_devices" stripe size="small">
            <el-table-column prop="asset_id" label="固资号" width="140" />
            <el-table-column prop="ip" label="IP" width="130" />
            <el-table-column prop="machine_type" label="机型" width="130" />
            <el-table-column prop="module" label="模块" min-width="200" />
          </el-table>
        </el-card>

        <!-- 未上线设备 -->
        <el-card shadow="never" class="node-section" style="margin-top: 16px">
          <template #header>
            <b>未上线设备</b>
            <el-tag size="small" type="warning" style="margin-left: 8px">
              {{ nodeOverviewData.offline_devices.length }} 台
            </el-tag>
          </template>
          <el-table v-if="nodeOverviewData.offline_devices.length" :data="nodeOverviewData.offline_devices" stripe size="small">
            <el-table-column prop="asset_id" label="固资号" width="140" />
            <el-table-column prop="ip" label="IP" width="130" />
            <el-table-column prop="machine_type" label="机型" width="130" />
            <el-table-column prop="module" label="模块" width="200" />
            <el-table-column prop="reason" label="未上线原因" min-width="200" />
          </el-table>
          <el-empty v-else description="该节点没有未上线设备" />
        </el-card>
      </template>
      <el-empty v-else description="选择可用区后查询资源概况" />
    </div>
  </el-tab-pane>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useZoneOverview } from '@/composables/useZoneOverview'

const {
  zone: nodeZoneSelected,
  loading: nodeLoading,
  syncing: nodeRefreshing,
  data: nodeOverviewData,
  error: nodeError,
  task: syncTask,
  pollCount,
  fetchOverview,
  cancelSync,
} = useZoneOverview()

// ... 其他代码保持不变 ...

async function onNodeOverview() {
  if (!nodeZoneSelected.value) return
  nodeLoading.value = true
  nodeOverviewData.value = null
  try {
    await fetchOverview(false)
  } catch {
    // 错误已在 composable 中处理
  } finally {
    nodeLoading.value = false
  }
}

async function onNodeForceRefresh() {
  if (!nodeZoneSelected.value) return
  nodeRefreshing.value = true
  try {
    await fetchOverview(true)
  } catch {
    // 错误已在 composable 中处理
  } finally {
    nodeRefreshing.value = false
  }
}
</script>
```

---

## 🎬 完整时间线示例

### 场景：首次使用

```
T+0s       用户首次访问系统
           → 浏览器弹出 SSO 登录窗口

T+5s       前端加载完毕
           → 用户选择 Zone = "zone_a"
           → 点击"查询资源概况"
           → 前端发送 GET /api/v1/zones/zone_a/overview

T+5.1s     后端检查：
           ✓ 本地无缓存
           ✗ profile 不存在（首次）
           → 返回 status: "login_required"
           → 返回 message: "请在浏览器中完成登录"
           
           前端接收到非成功状态：
           → syncTask.status = "login_required"
           → 显示"等待 SSO 登录完成..."
           → 启动轮询 (5s 间隔)

T+5.2s     用户在浏览器窗口中扫码

T+8s       用户扫码完成
           → 浏览器保存 cookies 文件

T+10.1s    前端轮询 #1
           GET /api/v1/zones/zone_a/overview/status
           
           后端检查：
           ✓ profile 存在且 mtime 有效
           → BrowserSession.is_login_valid() = True
           → 进入 _sync_from_cloud()
           → syncTask.status = "syncing"
           → syncTask.message = "正在从 IDCRM 采集..."
           → syncTask.progress = { step: 1, total: 2, percent: 0 }
           
           前端接收到 "syncing" 状态：
           → 切换为进度条显示
           → "步骤 1/2 (0%)"

T+12s      IDCRM 查询完成
           → 获得 10 个虚拟化机位
           → syncTask.progress = { step: 1, total: 2, percent: 50 }

T+15.1s    前端轮询 #2
           → 更新进度 (50%)

T+20s      TCUM 查询完成
           → 获得 8 台 TEZ 设备（6 online + 2 offline）
           → syncTask.progress = { step: 2, total: 2, percent: 100 }
           → syncTask.status = "success"
           → syncTask.data = { zone, free_count, online_devices, offline_devices, ... }

T+25.1s    前端轮询 #3
           → 收到 status = "success"
           → 停止轮询
           → 显示完整数据
           → Toast: "数据采集完成"

用户满意！✅
```

---

## 🔧 关键参数调优

### 等待超时

```python
# app/clients/browser_session.py
WAIT_FOR_LOGIN_TIMEOUT = 300  # 300 秒 = 5 分钟

# 如果用户在 5 分钟内没完成登录，返回超时
```

### 轮询间隔

```typescript
// web/src/composables/useZoneOverview.ts
POLL_INTERVAL_MS = 5000  // 5 秒轮询一次

// 可调整为：
// - 快速轮询（1s）：更实时但更多请求
// - 慢速轮询（10s）：减少请求但体验稍差
```

### 采集步骤超时

```python
# app/skills/idcrm_position_skill.py
WAIT_AFTER_GOTO = 4        # 页面加载后等 4 秒
WAIT_AFTER_FILTER = 8      # 查询后等 8 秒

# 可根据实际网络调整
```

---

## ✅ 实施清单

- [ ] 创建 `app/services/zone_sync_manager.py`
- [ ] 修改 `app/clients/browser_session.py` 添加 `wait_for_login_valid()` 和 `clear_profile()`
- [ ] 修改 `app/services/zone_resource_service.py` 支持任务管理
- [ ] 在 `app/routers/hosts.py` 添加 `/overview/status` 和 `/overview/cancel` 端点
- [ ] 创建 `web/src/composables/useZoneOverview.ts`
- [ ] 修改 `web/src/views/HostSearch.vue` 支持新的状态流程
- [ ] 测试：首次登录、强制刷新、取消采集
- [ ] 性能测试：确保轮询不会导致后端过载
- [ ] 用户体验测试：提示信息是否清晰

