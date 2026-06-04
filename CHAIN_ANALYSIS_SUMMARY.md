# "节点资源概况"完整链路分析总结

## 🎯 核心问题

**首次登录竞态条件**：前端调用 API 时，SSO 登录还未完成，导致采集失败。

---

## 📊 完整链路图

```
┌──────────────────────────────────────────────────────────────────┐
│ LAYER 1: 前端 Vue3 组件                                             │
│ HostSearch.vue (Line 209-302)                                    │
│ Tab: "节点资源概况"                                                 │
│ ├─ 函数: fetchNodeOverview(forceRefresh)                          │
│ ├─ 调用: GET /api/v1/zones/{zone}/overview                       │
│ └─ 显示: online_devices, offline_devices, free_count             │
└──────────────────────────────────────────────────────────────────┘
                          ↓ HTTP GET
┌──────────────────────────────────────────────────────────────────┐
│ LAYER 2: 后端 FastAPI 路由                                          │
│ app/routers/hosts.py (Line 434-452)                               │
│ GET /api/v1/zones/{zone}/overview                                │
│ ├─ 参数: zone, force_refresh (bool)                              │
│ ├─ 依赖: get_db_session (AsyncSession)                           │
│ └─ 调用: ZoneResourceService.get_zone_overview()                 │
└──────────────────────────────────────────────────────────────────┘
                          ↓ 业务逻辑
┌──────────────────────────────────────────────────────────────────┐
│ LAYER 3: 核心业务 Service                                           │
│ app/services/zone_resource_service.py                             │
│                                                                    │
│ 流程：                                                               │
│ 1. 读本地数据库 (select * from zone_snapshots)                    │
│    ├─ 缓存有效 (< 7 天) → ✅ 直接返回 (10ms)                     │
│    └─ 缓存无效/无数据 → 进入同步                                    │
│                                                                    │
│ 2. ❌ 问题点：不检查登录态！                                        │
│    直接调用 _sync_from_cloud()                                     │
│                                                                    │
│ 3. 调用浏览器自动化（下一层）                                        │
│    ├─ IDCRMPositionSkill.query_free_positions(idc)               │
│    └─ TCUMBrowserImpl.batch_search(asset_ids)                     │
│                                                                    │
│ 4. 写入本地数据库 (upsert zone_snapshots + zone_devices)          │
│    └─ last_sync_at = now                                          │
│                                                                    │
│ 5. 返回结果给前端                                                   │
└──────────────────────────────────────────────────────────────────┘
                          ↓ Playwright
┌──────────────────────────────────────────────────────────────────┐
│ LAYER 4: 浏览器自动化 - IDCRM 机位查询                              │
│ app/skills/idcrm_position_skill.py                                │
│ IDCRMPositionSkill.query_free_positions()                         │
│                                                                    │
│ SOP:                                                               │
│ 1. page.goto(IDCRM_URL) → wait_until: "domcontentloaded"        │
│ 2. await asyncio.sleep(WAIT_AFTER_GOTO = 4秒)                    │
│    ⚠️ 问题：此时 SSO 可能还未完成！                                │
│ 3. ❌ is_login_url(page.url) 检查 → 但不等待                      │
│    如果未登录 → 返回 free_count=None                               │
│ 4. 勾选筛选条件 (Ant Design Select 控件)                           │
│    ├─ 机位逻辑区域 = "通用虚拟化bonding区"                        │
│    ├─ 机房管理单元 = {idc}                                        │
│    └─ 不筛选机位状态（查全量）                                      │
│ 5. 点"查询"按钮 → 等待 8 秒 (WAIT_AFTER_FILTER)                   │
│ 6. 提取表格数据（支持翻页）                                         │
│    └─ 提取机位上的设备固资号 (TYSV*)                               │
│                                                                    │
│ 返回:                                                               │
│ {                                                                  │
│   "free_count": 10,                                               │
│   "used_count": 8,                                                │
│   "all_assets": ["TYSV001", "TYSV002", ...],                    │
│   "verified": True                                                 │
│ }                                                                  │
└──────────────────────────────────────────────────────────────────┘
                          ↓ 用同一 BrowserSession
┌──────────────────────────────────────────────────────────────────┐
│ LAYER 4b: 浏览器自动化 - TCUM 设备状态查询                         │
│ app/clients/tcum_browser.py                                       │
│ TCUMBrowserImpl.batch_search(asset_ids)                           │
│                                                                    │
│ SOP:                                                               │
│ 1. page.goto(TCUM_SEARCH_URL?key=TYSV001;TYSV002;...) 用;拼接    │
│ 2. await asyncio.sleep(DEFAULT_WAIT_AFTER_GOTO_MS / 1000 = 3.5秒) │
│ 3. await _try_finish_sso_flow(page) 尝试自动点击"登录"按钮          │
│ 4. ❌ is_login_url(page.url) 检查 → 仍可能未登录                  │
│ 5. 勾选"机器状态"列（显示设备状态）                                │
│ 6. 支持翻页（最多 10 页，每页 50 条）                              │
│ 7. 解析每行表格，标准化状态：                                      │
│    "运营中" → "online"                                            │
│    "维护中" → "maintenance"                                       │
│    "离线" → "offline"                                             │
│                                                                    │
│ 返回:                                                               │
│ [                                                                  │
│   {                                                                │
│     "asset_id": "TYSV001",                                        │
│     "ip": "10.0.0.1",                                             │
│     "machine_type": "M5s",                                        │
│     "module": "[N][TEZ]-[现网运营]",                              │
│     "status": "online"                                            │
│   },                                                               │
│   ...                                                              │
│ ]                                                                  │
└──────────────────────────────────────────────────────────────────┘
                          ↓ 共享 BrowserSession
┌──────────────────────────────────────────────────────────────────┐
│ LAYER 5: Playwright 浏览器会话管理                                  │
│ app/clients/browser_session.py (BrowserSession 单例)              │
│                                                                    │
│ 关键方法:                                                           │
│ ├─ page() - 打开新页面（自动关闭）                                 │
│ │  └─ 使用 _operation_lock 防止并发操作冲突                       │
│ │                                                                  │
│ ├─ is_login_valid() - ❌ 检查 cookies mtime (7天内有效)          │
│ │  └─ 文件不存在 → False (首次需扫码)                             │
│ │  └─ age_days >= 7 → False (需重新登录)                        │
│ │                                                                  │
│ └─ 持久化配置                                                      │
│    ├─ profile_dir: ~/.tez/browser-profile                        │
│    ├─ launch_persistent_context() - cookies 自动保存              │
│    └─ headless 模式 / ignore_https_errors                        │
│                                                                    │
│ ❌ 问题：is_login_valid() 不等待，只检查文件 mtime                 │
│    SSO 过程是异步的，文件写入有延迟                                  │
└──────────────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────────────┐
│ LAYER 6: SQLite 本地数据库                                         │
│ file:///data/tez.db                                               │
│                                                                    │
│ 表 1: zone_snapshots (zone_resource_service.py)                  │
│ ├─ zone (PK)              │ 可用区名                               │
│ ├─ idc                    │ 物理机房                               │
│ ├─ total_positions        │ 虚拟化机位总数                         │
│ ├─ free_count             │ 空闲机位数                             │
│ ├─ used_count             │ 已用机位数                             │
│ ├─ online_count           │ 已上线设备数                           │
│ ├─ offline_count          │ 未上线设备数                           │
│ ├─ non_tez_count          │ 非 TEZ 设备数                         │
│ ├─ last_sync_at           │ 上次同步时间 ⬅️ 7天过期策略关键      │
│ └─ raw_data (JSON)        │ 原始采集结果                           │
│                                                                    │
│ 表 2: zone_devices (zone_resource_service.py)                    │
│ ├─ zone                   │ 所属可用区                             │
│ ├─ asset_id               │ 固资号 TYSV*                          │
│ ├─ ip                     │ IP 地址                               │
│ ├─ machine_type           │ 机型（如 M5s）                        │
│ ├─ module                 │ 模块路径                               │
│ ├─ status                 │ 设备状态（online/offline/maintenance）│
│ ├─ category               │ 分类（online/offline/non_tez）        │
│ ├─ is_tez                 │ 是否 TEZ 设备                         │
│ └─ reason                 │ 未上线原因                             │
│                                                                    │
│ 缓存策略：                                                          │
│ ├─ 有效期：7 天                                                    │
│ ├─ 刷新触发：过期 OR force_refresh=true                           │
│ └─ 存储：Upsert (新数据覆盖旧数据)                                 │
└──────────────────────────────────────────────────────────────────┘
```

---

## 🔴 关键问题点（按执行顺序）

### 问题 1: 后端不检查登录态 (最严重)

**位置**: `app/services/zone_resource_service.py` Line 102-114

```python
async def _sync_from_cloud(self, zone: str) -> dict[str, Any] | None:
    # ❌ 直接调用，不检查登录态！
    skill = IDCRMPositionSkill()
    pos_result = await skill.query_free_positions(idc)
```

**症状**: 首次登录时，即使 cookies 文件不存在或还没保存，仍然启动采集

**解决**: 在 `get_zone_overview()` 中检查 `BrowserSession.is_login_valid()`

---

### 问题 2: IDCRM 等待时间固定且过短

**位置**: `app/skills/idcrm_position_skill.py` Line 34

```python
WAIT_AFTER_GOTO = 4  # 仅 4 秒
```

**症状**: SSO 流程通常需要 5-10 秒，4 秒时可能还在登录页

**解决**: 增加等待时间 OR 动态等待直到"查询"按钮出现

---

### 问题 3: IDCRM 不等待 SSO 完成

**位置**: `app/skills/idcrm_position_skill.py` Line 64-65

```python
if is_login_url(page.url):
    return {"free_count": None, "message": "数全通登录态失效，请扫码登录"}
# ❌ 检查后立即返回，不等待
```

**症状**: 检测到登录页后直接返回失败，不重试或等待

**解决**: 增加重试机制，或在返回前等待一段时间再检查

---

### 问题 4: TCUM SSO 中转流程有超时风险

**位置**: `app/clients/tcum_browser.py` Line 232

```python
while is_login_url(page.url) and asyncio.get_running_loop().time() < deadline:
    # deadline 取决于外层调用，可能被中断
```

**症状**: SSO 超时时可能返回登录页，导致采集失败

**解决**: 增加重试机制，或支持用户在浏览器中手动登录后重试

---

### 问题 5: BrowserSession.is_login_valid() 只检查文件，不等待

**位置**: `app/clients/browser_session.py` Line 118-137

```python
@staticmethod
def is_login_valid() -> bool:
    # ❌ 只检查文件 mtime，不等待
    if not cookies_file.exists():
        return False
```

**症状**: SSO 登录后，cookies 文件从磁盘写入有延迟，立即查询可能失败

**解决**: 增加 `wait_for_login_valid()` 方法，支持阻塞等待

---

## 📋 关键代码片段汇总

### 1. 前端组件 - fetchNodeOverview()

**文件**: `web/src/views/HostSearch.vue` Line 487-507

```typescript
async function fetchNodeOverview(forceRefresh = false) {
  const zone = nodeZoneSelected.value
  if (!zone) return

  const url = `/api/v1/zones/${encodeURIComponent(zone)}/overview${forceRefresh ? '?force_refresh=true' : ''}`
  const resp = await fetch(url).then(r => r.json())

  nodeOverviewData.value = {
    positions: {
      zone: resp.zone,
      idc: resp.idc,
      free_count: resp.free_count,
      total_positions: resp.total_positions,
      message: resp.message || '',
    },
    offline_devices: resp.offline_devices || [],
    online_devices: resp.online_devices || [],
    from_cache: resp.from_cache,
    last_sync_at: resp.last_sync_at,
  }
}
```

**关键**:
- 直接 fetch，无重试机制
- 无超时处理
- 无等待提示

---

### 2. 后端路由 - get_zone_overview()

**文件**: `app/routers/hosts.py` Line 434-452

```python
@zone_router.get("/{zone}/overview", summary="节点资源概况...")
async def get_zone_overview(
    zone: str,
    force_refresh: bool = False,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    svc = ZoneResourceService(session)
    return await svc.get_zone_overview(zone, force_refresh=force_refresh)
```

**关键**:
- 直接调用 Service，无登录态检查
- 无异常处理
- 同步阻塞（可能 30+ 秒）

---

### 3. 业务逻辑 - get_zone_overview()

**文件**: `app/services/zone_resource_service.py` Line 32-66

```python
async def get_zone_overview(self, zone: str, force_refresh: bool = False) -> dict[str, Any]:
    # Step 1: 读本地数据库
    snapshot = await self._get_snapshot(zone)

    if snapshot and not force_refresh:
        if snapshot.last_sync_at and (datetime.now() - snapshot.last_sync_at) < timedelta(days=SYNC_EXPIRE_DAYS):
            devices = await self._get_devices(zone)
            return self._build_response(snapshot, devices, from_cache=True)

    # Step 2: 过期或无数据 → 从云端同步
    # ❌ 这里应该检查登录态！
    log.info("zone_resource.sync_needed", zone=zone, force=force_refresh)
    result = await self._sync_from_cloud(zone)  # <-- 问题位置

    if result:
        return result

    # Step 3: 同步失败但有旧数据，仍然返回旧数据
    if snapshot:
        devices = await self._get_devices(zone)
        resp = self._build_response(snapshot, devices, from_cache=True)
        resp["sync_warning"] = "同步失败，显示的是上次缓存数据"
        return resp

    return {"zone": zone, "message": "暂无数据，且同步失败"}
```

**关键**:
- 缓存命中时毫秒级（快速路径）
- 无缓存时触发同步（阻塞 20-30 秒）
- 无登录态预检查

---

### 4. 浏览器自动化 - IDCRM 查询

**文件**: `app/skills/idcrm_position_skill.py` Line 51-170

```python
async def query_free_positions(self, idc: str) -> dict[str, Any]:
    base_url = self._settings.idcrm_base_url.rstrip("/") + "/db/positions"
    timeout_ms = self._settings.browser_page_timeout_ms

    async with BrowserSession.page() as page:
        # 1. 打开页面
        try:
            await page.goto(base_url, wait_until="domcontentloaded", timeout=timeout_ms)
        except Exception:
            pass
        await asyncio.sleep(self.WAIT_AFTER_GOTO)  # 4 秒

        # ❌ 检查后立即返回，不等待
        if is_login_url(page.url):
            return {"free_count": None, "message": "数全通登录态失效，请扫码登录"}

        # 带校验的查询（最多重试 MAX_RETRY=2 次）
        for attempt in range(1 + self.MAX_RETRY):
            if attempt > 0:
                log.warning("idcrm_skill.retry", attempt=attempt)
                try:
                    await page.goto(base_url, wait_until="domcontentloaded", timeout=timeout_ms)
                except Exception:
                    pass
                await asyncio.sleep(self.WAIT_AFTER_GOTO)

            # ... 筛选逻辑 ...
            
            # 2. 填筛选条件
            ok1 = await self._ant_select_with_search(page, self.IDX_LOGIC_AREA, ...)
            ok2 = await self._ant_select_with_search(page, self.IDX_IDC_UNIT, ...)
            
            # 3. 点查询按钮
            await self._click_query_button(page)
            await asyncio.sleep(self.WAIT_AFTER_FILTER)  # 8 秒

            # 4. 提取结果（支持翻页）
            rows = await self._extract_all_pages(page)
            
            # 5. 统计和返回
            # ...
```

**关键**:
- WAIT_AFTER_GOTO = 4 秒（可能不够）
- 校验失败最多重试 2 次
- 无 SSO 完成等待机制

---

### 5. 浏览器自动化 - TCUM 查询

**文件**: `app/clients/tcum_browser.py` Line 72-155

```python
async def batch_search(self, asset_ids: list[str]) -> list[dict[str, Any]]:
    # ...
    async with BrowserSession.page() as page:
        try:
            await page.goto(url, wait_until="networkidle", timeout=timeout_ms)
        except Exception:
            pass

        await asyncio.sleep(self.DEFAULT_WAIT_AFTER_GOTO_MS / 1000)  # 3.5 秒
        await self._try_finish_sso_flow(page)  # 尝试自动点击"登录"

        # ❌ 如果此时仍未登录，立即返回错误
        if is_login_url(page.url):
            raise BrowserAuthExpired("TCUM 登录态失效，请重新扫码登录")

        # 勾选"机器状态"列
        await self._enable_machine_status_column(page)

        # 翻页提取所有结果
        for page_num in range(max_pages):
            rows: list[list[str]] = []
            # ...
```

**关键**:
- DEFAULT_WAIT_AFTER_GOTO_MS = 3500 ms（3.5 秒）
- _try_finish_sso_flow() 有 30 秒超时
- SSO 中转失败直接抛异常

---

### 6. 登录态检查 - BrowserSession

**文件**: `app/clients/browser_session.py` Line 117-137

```python
@staticmethod
def is_login_valid() -> bool:
    s = get_settings()
    profile_dir = Path(s.browser_profile_dir)
    cookies_file = profile_dir / "Default" / "Cookies"
    if not cookies_file.exists():
        return False  # ❌ 首次返回 False
    try:
        mtime = cookies_file.stat().st_mtime
    except OSError:
        return False
    import time
    age_days = (time.time() - mtime) / 86400
    return age_days < s.browser_login_valid_days  # 默认 7 天
```

**关键**:
- 仅检查文件是否存在 + mtime
- 不等待文件创建
- 不等待 SSO 完成

---

## 🛠️ 改进方案 3 要点

### 方案 A: 主动等待登录 (推荐)

```python
# app/clients/browser_session.py
@staticmethod
def wait_for_login_valid(timeout_sec: int = 300) -> bool:
    """阻塞等待登录态有效"""
    start = time.time()
    while time.time() - start < timeout_sec:
        if BrowserSession.is_login_valid():
            return True
        time.sleep(2)
    return False

# app/services/zone_resource_service.py
async def get_zone_overview(self, zone: str, ...) -> dict:
    # ...
    if not BrowserSession.profile_exists():
        return {"status": "login_required", "message": "请在浏览器中完成登录..."}
    
    if not BrowserSession.is_login_valid():
        return {"status": "login_expired", "message": "登录态过期..."}
    
    # 如果进入了 _sync_from_cloud，说明登录态已有效
    result = await self._sync_from_cloud(zone)
```

**优点**:
- ✅ 逻辑清晰
- ✅ 客户端代码简单
- ❌ 后端阻塞等待（可能浪费线程）

### 方案 B: 前端轮询等待 (最优)

```typescript
// 前端
async function fetchOverviewWithWait() {
  while (true) {
    const resp = await fetch(`/api/v1/zones/{zone}/overview`)
    if (resp.status === 'login_required') {
      // 等待 5 秒后重试
      await sleep(5000)
      continue
    }
    return resp
  }
}

// 后端
if not BrowserSession.profile_exists():
    return {"status": "login_required", "retry_after": 60}
```

**优点**:
- ✅ 后端不阻塞
- ✅ 前端可显示进度
- ✅ 用户可取消
- ✅ 支持多并发请求

---

## ⏱️ 时间预算

### 首次查询 (SSO 未完成)

```
T+0s    前端发送 GET /api/v1/zones/zone_a/overview
T+0.1s  后端检查 profile → 不存在 → 返回 login_required
T+0.1s  前端轮询 #1
T+5s    用户完成 SSO 扫码 → cookies 文件保存
T+5s    前端轮询 #2 → 检查登录态有效 → 启动采集
T+5.5s  IDCRM 查询开始 (wait 4s + 操作 ~2s)
T+7.5s  IDCRM 查询完成 → 返回 10 个虚拟化机位
T+8s    TCUM 查询开始 (wait 3.5s + 翻页 ~3s)
T+14s   TCUM 查询完成 → 返回 8 台设备
T+14.5s 数据写入数据库 + 构建响应
T+20s   前端轮询 #3 → status=success → 显示数据

总时间：20 秒（从首次查询到最终显示数据）
```

### 缓存命中查询

```
T+0s    前端发送 GET /api/v1/zones/zone_a/overview
T+0.01s 后端查询本地数据库 → 命中 + 有效
T+0.02s 后端返回数据
T+0.1s  前端更新 UI

总时间：100ms
```

---

## 📌 实施步骤

1. ✅ 分析完成（本文档）
2. ⏳ 实现 `wait_for_login_valid()` 方法
3. ⏳ 修改 `get_zone_overview()` 添加登录态检查
4. ⏳ 新增 `/status` 和 `/cancel` API 端点
5. ⏳ 前端实现轮询逻辑
6. ⏳ 前端 UI 添加进度显示
7. ⏳ 集成测试（首次登录、强制刷新、取消）

