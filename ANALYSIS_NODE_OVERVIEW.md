# TEZ Operator - 节点资源概况功能完整分析

## 📋 概览

"节点资源概况"是 TEZ 运维系统中的关键功能，用于查看特定可用区（Zone）的虚拟化机位和设备上线情况。该功能涉及**浏览器自动化**跨越多个外部系统（IDCRM、TCUM）的数据采集，以及**本地数据库缓存**确保快速响应。

---

## 🏗️ 架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                    前端 Vue3 + TS                              │
│  HostSearch.vue - "节点资源概况" Tab                            │
│  fetchNodeOverview() → /api/v1/zones/{zone}/overview          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              后端 FastAPI Router                               │
│  GET /api/v1/zones/{zone}/overview                            │
│  ↓                                                             │
│  ZoneResourceService.get_zone_overview()                      │
│  ├─ 读本地数据库（快速响应）                                   │
│  └─ 若数据过期/无数据 → 触发异步同步                           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│         浏览器自动化采集层（关键：跨平台 SSO）                   │
│  IDCRMPositionSkill → 数全通机位查询                           │
│  TCUMBrowserImpl → TCUM 设备状态查询                            │
│  (均通过 Playwright + 共享 BrowserSession)                     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              SQLite 本地数据库                                  │
│  zone_snapshots - 每个可用区一条快照                           │
│  zone_devices - 设备清单                                       │
│  (7天缓存，过期自动刷新)                                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎯 问题根源

**首次登录时的竞态条件**：

```
Timeline:
─────────────────────────────────────────────────────────

1. 用户首次访问系统，需要 iOA SSO 登录
   └─ BrowserSession.is_login_valid() 检查 cookies 文件 mtime
   └─ 文件不存在 → 返回 False
   └─ 记录警告: "login_state_expired_or_missing"

2. 前端立即调用 /api/v1/zones/{zone}/overview
   └─ 后端读本地数据库 (无数据)
   └─ 触发 _sync_from_cloud() → IDCRMPositionSkill.query_free_positions()
   └─ Playwright 启动浏览器窗口
     └─ 访问 IDCRM 页面
     └─ **此时浏览器可能还未完成 SSO 登录流程**
     └─ 返回登录页 / 空结果
   └─ 后端返回 free_count=0 的结果

3. 用户在浏览器中完成扫码登录
   └─ Cookies 文件写入成功
   └─ 此时再查询才能获得真实数据
```

**关键问题**：
- ❌ 浏览器 SSO 登录是**异步的、手动的**（需要用户扫码）
- ❌ 后端 API 不等待登录完成就立即返回查询结果
- ❌ 两个不同的 Playwright 页面操作（IDCRM、TCUM）没有同步协调

---

## 📁 代码位置与文件清单

### 前端代码

#### 1. **主视图组件**
```
/web/src/views/HostSearch.vue
```
- **Tab 名**: `"节点资源概况"` (name: `node_overview`)
- **关键函数**:
  - `fetchNodeOverview(forceRefresh = false)` - 获取数据
  - `onNodeOverview()` - 查询按钮处理
  - `onNodeForceRefresh()` - 强制刷新按钮处理
- **API 调用**: 
  ```typescript
  const url = `/api/v1/zones/${encodeURIComponent(zone)}/overview${forceRefresh ? '?force_refresh=true' : ''}`
  const resp = await fetch(url).then(r => r.json())
  ```
- **返回数据结构**:
  ```typescript
  interface NodeOverviewData {
    positions: { zone, idc, free_count, total_positions, message }
    online_devices: { asset_id, ip, machine_type, module }[]
    offline_devices: { asset_id, ip, machine_type, module, reason }[]
    from_cache: boolean  // 是否来自缓存
    last_sync_at: string // 上次同步时间
  }
  ```

#### 2. **API 客户端**
```
/web/src/api/hosts.ts
```
- 获取 zone 列表: `listZones()`
- 获取 zone 信息: `onZoneInfoQuery()`
- 导出: `exportHostsExcel()`

### 后端代码

#### 1. **API 路由**
```
/app/routers/hosts.py (Line 434-452)
```
```python
@zone_router.get(
    "/{zone}/overview",
    summary="节点资源概况（本地数据库优先，7天过期自动刷新）",
)
async def get_zone_overview(
    zone: str,
    force_refresh: bool = False,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """获取可用区资源概况（本地数据库模式）。
    
    - 默认读本地数据库（毫秒级响应）
    - 数据超过7天自动触发后台同步
    - force_refresh=true 手动强制刷新
    """
    from app.services.zone_resource_service import ZoneResourceService
    
    svc = ZoneResourceService(session)
    return await svc.get_zone_overview(zone, force_refresh=force_refresh)
```

**关键参数**:
- `zone`: 可用区名，如 `zone_a`, `ap-sh-2-2`
- `force_refresh`: true 时忽略缓存，强制从云端刷新

#### 2. **核心业务逻辑 Service**
```
/app/services/zone_resource_service.py
```

**主要方法**:
```python
async def get_zone_overview(self, zone: str, force_refresh: bool = False) -> dict[str, Any]
```

**执行流程**:
```python
# Step 1: 读本地数据库
snapshot = await self._get_snapshot(zone)

# Step 2: 检查有效期（7天）
if snapshot and not force_refresh:
    if (datetime.now() - snapshot.last_sync_at) < timedelta(days=SYNC_EXPIRE_DAYS):
        # 未过期，返回缓存（毫秒级）
        return self._build_response(snapshot, devices, from_cache=True)

# Step 3: 过期或无数据 → 从云端同步
result = await self._sync_from_cloud(zone)

# Step 4: 同步失败但有旧数据，返回旧数据 + 警告
if not result and snapshot:
    resp = self._build_response(snapshot, devices, from_cache=True)
    resp["sync_warning"] = "同步失败，显示的是上次缓存数据"
    return resp
```

**关键内部方法**:
- `_get_snapshot(zone)` - 读快照表
- `_get_devices(zone)` - 读设备表
- `_sync_from_cloud(zone)` - **关键**：触发浏览器自动化采集
- `_save_snapshot(...)` - 写入本地库（upsert）
- `_build_response(...)` - 组装返回结果

#### 3. **浏览器自动化 - IDCRM 机位查询**
```
/app/skills/idcrm_position_skill.py
```

**关键方法**:
```python
async def query_free_positions(self, idc: str) -> dict[str, Any]
```

**SOP**:
1. 打开 IDCRM 机位列表页：`/db/positions`
2. 等待 DOM 加载 + SSO 流程（`WAIT_AFTER_GOTO = 4` 秒）
3. 检查登录态：
   ```python
   if is_login_url(page.url):
       return {"free_count": None, "message": "数全通登录态失效，请扫码登录"}
   ```
4. 勾选"机位放置设备(服务器)"列
5. 设置分页大小为 100 条/页
6. 填筛选条件：
   - 机位逻辑区域 = "通用虚拟化bonding区"
   - 机房管理单元 = {idc}（不筛选机位状态，查全量）
7. 点查询按钮
8. 支持翻页，提取所有行
9. 统计各状态 + 提取机位上的设备固资号

**关键配置**:
```python
WAIT_AFTER_GOTO = 4  # 页面加载后等待 4 秒（给 SSO 完成）
WAIT_AFTER_FILTER = 8  # 查询后等待 8 秒（让结果渲染）
MAX_RETRY = 2  # 校验失败最多重试 2 次
```

**返回数据**:
```python
{
    "total_positions": int,      # 虚拟化机位总数
    "free_count": int,           # 空闲机位数
    "used_count": int,           # 已用机位数
    "other_count": int,          # 其他状态机位数
    "all_assets": [str],         # 所有机位上的设备固资号
    "message": str,              # 汇总信息
}
```

#### 4. **浏览器自动化 - TCUM 设备状态查询**
```
/app/clients/tcum_browser.py
```

**关键方法**:
```python
async def batch_search(self, asset_ids: list[str]) -> list[dict[str, Any]]
```

**功能**:
- 输入多个固资号（用`;`拼接）
- 一次查询获取所有设备的状态信息
- 支持翻页（最多 10 页，每页 50 条）
- 自动勾选"机器状态"列
- 处理 SSO 中转流程

**返回字段** (每条设备):
```python
{
    "asset_id": str,          # 固资号
    "ip": str,                # IP 地址
    "machine_type": str,      # 机型
    "module": str,            # 模块路径
    "status": "online" | "offline" | "maintenance",  # 标准化状态
    "city": str,
    "owner": str,
    "backup_owners": [str],
    "use_years": float,
    "_source": "tcum-browser",
}
```

**关键注意**：
- 状态中英文映射（采集层完成）
  ```python
  "运营中" → "online"
  "维护中" → "maintenance"
  "离线" → "offline"
  ```

#### 5. **Playwright BrowserSession 单例**
```
/app/clients/browser_session.py
```

**设计要点**:
- **全局单例**: 全应用只有 1 个 BrowserContext
- **共享登录态**: 所有 Impl（IDCRM、TCUM 等）通过 `new_page()` 复用同一个 session 的 cookies
- **持久化**：
  ```python
  launch_persistent_context(
      user_data_dir=str(profile_dir),  # 如: ~/.tez/browser-profile
      headless=s.browser_headless,
      ignore_https_errors=s.browser_ignore_https_errors,
  )
  ```
- **登录态检查**:
  ```python
  @staticmethod
  def is_login_valid() -> bool:
      """检查 cookies 文件 mtime 是否在 N 天内"""
      cookies_file = profile_dir / "Default" / "Cookies"
      if not cookies_file.exists():
          return False  # 首次，需要扫码
      age_days = (time.time() - mtime) / 86400
      return age_days < s.browser_login_valid_days  # 默认 7 天
  ```
- **操作锁**: `_operation_lock` 防止并发 Playwright 操作冲突

#### 6. **数据模型**
```
/app/models/zone_snapshot.py
```

**ZoneSnapshot** (zone_snapshots 表):
```python
zone: str (PK)           # 可用区名
idc: str                 # 对应的物理机房
total_positions: int     # 虚拟化机位总数
free_count: int          # 空闲机位
used_count: int          # 已用机位
online_count: int        # 已上线设备数
offline_count: int       # 未上线设备数
last_sync_at: datetime   # 上次同步时间
raw_data: dict (JSON)    # 原始采集结果备份
```

**ZoneDevice** (zone_devices 表):
```python
zone: str                # 所属可用区
asset_id: str            # 固资号
ip: str                  # IP
machine_type: str        # 机型
module: str              # 模块
status: str              # 设备状态
category: str            # "online" / "offline" / "non_tez"
is_tez: bool             # 是否 TEZ 设备
reason: str              # 未上线原因（如适用）
```

---

## 🔄 数据流程详解

### 场景 1: 首次查询（无本地缓存）

```
前端点击"查询资源概况"
    ↓
GET /api/v1/zones/zone_a/overview
    ↓
ZoneResourceService.get_zone_overview('zone_a', force_refresh=False)
    ↓
[检查本地库] snapshot = await _get_snapshot('zone_a')
    ├─ 无数据 → 进入同步流程
    └─ 有数据且未过期 → 返回缓存（快速路径）
    
进入 _sync_from_cloud('zone_a')
    ↓
[IDCRM] IDCRMPositionSkill().query_free_positions(idc='宁波边缘二区（移动）')
    ├─ Playwright 打开 IDCRM 页面
    ├─ **等待 4 秒** (给 SSO 完成)
    ├─ ⚠️  如果 SSO 未完成 → 返回登录页 → 返回 free_count=None
    ├─ 勾选筛选条件 + 点查询
    ├─ 提取所有虚拟化机位 + 机位上的固资号
    └─ 返回 { free_count=10, all_assets=['TYSV001', 'TYSV002', ...] }
    
[TCUM] TCUMBrowserImpl().batch_search(all_assets)
    ├─ Playwright 打开 TCUM 页面
    ├─ **等待 3.5 秒** + **尝试完成 SSO 中转**
    ├─ 搜索多个固资号（用;拼接）
    ├─ 勾选"机器状态"列
    ├─ 翻页提取所有结果
    ├─ 解析每行，标准化状态（运营中→online）
    └─ 返回 { asset_id, status, module, ... }

[数据库] _save_snapshot()
    ├─ 分类: online_devices, offline_devices, non_tez_devices
    ├─ Upsert ZoneSnapshot + 插入 ZoneDevice 记录
    └─ 记录 last_sync_at = now

[响应] _build_response()
    ├─ 从数据库读回刚写入的数据
    └─ 返回 {
         zone, idc, free_count, total_positions,
         online_devices: [{asset_id, ip, machine_type, module}],
         offline_devices: [{..., reason}],
         from_cache: False,
         last_sync_at: "2026-05-25T10:30:45.123456",
         message: "虚拟化机位: 20（空闲10/已用10），TEZ已上线15台, 未上线2台"
       }

前端展示结果
```

### 场景 2: 缓存有效期内查询（快速路径）

```
GET /api/v1/zones/zone_a/overview
    ↓
ZoneResourceService.get_zone_overview('zone_a', force_refresh=False)
    ↓
snapshot = await _get_snapshot('zone_a')
    ├─ 存在且 (now - last_sync_at) < 7 days
    └─ ✅ 直接返回缓存（毫秒级响应）
    
返回 {
    ...,
    from_cache: True,
    last_sync_at: "2026-05-18T...",  # 7 天前的数据
    message: "虚拟化机位: 20..."
}

前端显示"本地缓存数据（上次同步: 2026-05-18...）"的 info alert
```

### 场景 3: 强制刷新

```
前端点击"🔄 强制刷新"按钮
    ↓
GET /api/v1/zones/zone_a/overview?force_refresh=true
    ↓
ZoneResourceService.get_zone_overview('zone_a', force_refresh=True)
    ├─ 忽略缓存有效期检查
    └─ 进入 _sync_from_cloud()
    
[同场景 1 相同]
    ↓
返回最新采集的数据 (from_cache: False)

前端显示 toast: "数据已从云端刷新"
```

---

## ⚠️ 首次登录竞态条件问题分析

### 问题表现

```
时间线（毫秒级）:

T+0ms:    用户首次访问系统
          → BrowserSession 尚未初始化

T+500ms:  前端加载完毕
          → 用户在浏览器地址栏看到 SSO 登录弹窗

T+1000ms: 用户开始扫码登录
          → 浏览器 SSO 流程中

T+1500ms: 前端: 用户点"查询资源概况"
          → API 立即返回请求
          ❌ **此时 cookies 还没保存**

T+2000ms: 后端: GET /api/v1/zones/zone_a/overview
          → ZoneResourceService 触发 _sync_from_cloud()
          → IDCRMPositionSkill 启动第一个 Playwright 页面
          ├─ page.goto(IDCRM_URL)
          ├─ ⚠️  此时这个新的 Playwright 窗口使用的是新的登录状态
          ├─ **SSO 流程又要重新走一遍**
          └─ 4 秒后，BrowserSession.is_login_valid() 仍返回 False
             (因为 cookies 文件要到 T+5000ms 才会被写入)
          └─ 返回登录页，采集失败
          └─ 数据库中写入 free_count=0 / all_assets=[]

T+5000ms: 用户在浏览器中完成扫码登录
          → cookies 文件被 OS 保存到磁盘

T+3000ms: 前端收到 API 响应
          → { free_count: 0, message: "未知可用区" }
          ❌ **用户看到空结果**

T+5500ms: 用户刷新页面后重新查询
          → 此时 cookies 有效
          → 采集成功
          ✅ **显示正确的数据**
```

### 根本原因

1. **异步 SSO 登录**：用户在浏览器中手动扫码，不受后端控制
2. **无等待机制**：后端 API 不检查 SSO 是否完成就立即查询
3. **Cookies 文件写入延迟**：扫码→token 获取→文件写入，全链路有延迟
4. **并发浏览器操作**：IDCRM 和 TCUM 各用一个页面，可能重复触发 SSO

---

## 🔧 设计问题与改进方案

### 问题 1：登录态检查时机不对

**现状**:
```python
# TCUMBrowserImpl.get_by_asset()
if not BrowserSession.is_login_valid():
    log.warning("tcum_browser.login_state_expired_or_missing", ...)
# ⚠️ 仅记录日志，继续执行（可能失败）
```

**改进**:
```python
# 选项 A: 主动等待（阻塞）
@staticmethod
def wait_for_login_valid(timeout_sec=300) -> bool:
    """阻塞等待，直到登录态有效"""
    start = time.time()
    while time.time() - start < timeout_sec:
        if BrowserSession.is_login_valid():
            return True
        time.sleep(2)  # 每 2 秒检查一次
    return False  # 超时

# 在 _sync_from_cloud 开始前调用
if not BrowserSession.wait_for_login_valid(timeout_sec=300):
    return {
        "zone": zone,
        "message": "登录态无效，等待超时。请检查浏览器窗口是否需要扫码"
    }

# 选项 B: 返回等待状态，让前端轮询
return {
    "zone": zone,
    "status": "waiting_for_login",
    "message": "系统检测到首次登录，请在弹出的浏览器窗口中完成 SSO 扫码登录（需要 2-5 分钟）",
    "retry_after_seconds": 60,
}
```

### 问题 2：SSO 中转流程不完整

**现状**:
```python
# TCUMBrowserImpl.batch_search()
await asyncio.sleep(self.DEFAULT_WAIT_AFTER_GOTO_MS / 1000)  # 3.5 秒
await self._try_finish_sso_flow(page)  # 尝试自动点击确认

# ⚠️ 3.5 秒可能不够，SSO 还在加载
```

**改进**:
```python
async def _try_finish_sso_flow(self, page: Any, timeout_sec: int = 60) -> bool:
    """改进的 SSO 完成等待，支持更长的超时"""
    click_terms = ("登录", "确认", "确定", "继续", "进入系统")
    deadline = asyncio.get_running_loop().time() + timeout_sec
    
    while is_login_url(page.url) and asyncio.get_running_loop().time() < deadline:
        # 尝试点击各种确认按钮
        clicked = False
        for term in click_terms:
            try:
                btn = page.get_by_role("button", name=term).first
                if await btn.is_visible(timeout=500):
                    log.info("sso_click", text=term)
                    await btn.click()
                    await asyncio.sleep(3)
                    clicked = True
                    break
            except Exception:
                continue
        
        if not clicked:
            await asyncio.sleep(2)  # 继续等待
        
        # 检查是否已跳转离开登录页
        if not is_login_url(page.url):
            log.info("sso_complete", url=page.url)
            return True
    
    return not is_login_url(page.url)

# 调用时
success = await self._try_finish_sso_flow(page, timeout_sec=120)  # 给 2 分钟
if not success:
    raise BrowserAuthExpired("SSO 登录流程超时")
```

### 问题 3：首次登录时无初始化提示

**改进**:
```python
# app/routers/hosts.py
@zone_router.get("/{zone}/overview", ...)
async def get_zone_overview(zone: str, ...) -> dict[str, Any]:
    # 新增：检查是否需要初始化登录
    if not BrowserSession.profile_exists():
        return {
            "zone": zone,
            "idc": ZONE_IDC_MAPPING.get(zone),
            "status": "login_required",
            "message": (
                "系统首次启动，需要进行身份验证。请查看弹出的浏览器窗口，"
                "使用 SSO（iOA、企业微信等）完成登录。通常需要 1-5 分钟。"
            ),
            "next_action": "请稍候，系统会自动重试数据采集",
            "free_count": None,
            "online_devices": [],
            "offline_devices": [],
        }
    
    # 如果 profile 存在但登录态过期
    if not BrowserSession.is_login_valid():
        return {
            "zone": zone,
            "status": "login_expired",
            "message": "登录态已过期（超过 7 天），请重新扫码登录",
            "next_action": "请在浏览器窗口中点击登录",
            "free_count": None,
        }
    
    # 正常流程
    svc = ZoneResourceService(session)
    return await svc.get_zone_overview(zone, force_refresh=force_refresh)
```

### 问题 4：IDCRM 页面加载等待时间不确定

**改进**:
```python
# app/skills/idcrm_position_skill.py
async def query_free_positions(self, idc: str) -> dict[str, Any]:
    # 使用更智能的等待策略
    async with BrowserSession.page() as page:
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        except Exception:
            pass
        
        # 固定等待 + 动态等待
        await asyncio.sleep(self.WAIT_AFTER_GOTO)  # 固定 4 秒
        
        # 动态等待：直到页面上出现查询按钮
        try:
            await page.locator('button:has-text("查 询")').wait_for(timeout=10000)
            log.info("idcrm.query_btn_appeared")
        except Exception:
            log.warning("idcrm.query_btn_timeout")
        
        # 检查登录态
        if is_login_url(page.url):
            # 更长的超时尝试完成 SSO
            max_wait = 60  # 最多等 60 秒
            start = time.time()
            while is_login_url(page.url) and (time.time() - start) < max_wait:
                await asyncio.sleep(3)
                page = await page.reload()
            
            if is_login_url(page.url):
                return {"free_count": None, "message": "SSO 登录超时"}
        
        # 继续后续操作...
```

---

## 📊 缓存策略

### 缓存配置

| 配置 | 值 | 说明 |
|------|-----|------|
| 缓存有效期 | 7 天 | 在 `zone_resource_service.py` 中 |
| 数据库表 | `zone_snapshots` | 快照（每个 zone 一条） |
| 设备表 | `zone_devices` | 每台设备一条 |
| 更新策略 | Upsert | 新的同步覆盖旧数据 |
| 同步触发 | 过期或手动 force_refresh | 不自动后台刷新 |

### 缓存键

```python
# 主键：zone 名称
# 例如：zone_a, ap-sh-2-2, 宁波边缘二区

# 缓存查询：
# SELECT * FROM zone_snapshots WHERE zone = 'zone_a'
```

### 缓存失效

```python
# 手动失效 - 前端调用
GET /api/v1/zones/zone_a/overview?force_refresh=true

# 自动失效 - 超过 7 天
if (datetime.now() - snapshot.last_sync_at) >= timedelta(days=SYNC_EXPIRE_DAYS):
    await self._sync_from_cloud(zone)
```

---

## 🌐 API 详细规范

### 端点：GET /api/v1/zones/{zone}/overview

#### 请求

```http
GET /api/v1/zones/zone_a/overview?force_refresh=false HTTP/1.1
Host: localhost:8000
Authorization: Bearer <token>
```

**参数**:

| 名称 | 类型 | 必需 | 说明 |
|------|------|------|------|
| zone | string | ✅ | 可用区名，如 `zone_a`, `ap-sh-2-2` |
| force_refresh | boolean | | 强制从云端刷新，默认 false |

#### 响应 (成功 200)

```json
{
  "zone": "zone_a",
  "idc": "宁波边缘二区（移动）",
  "total_positions": 20,
  "free_count": 10,
  "used_count": 8,
  "total_assets": 16,
  
  "online_devices": [
    {
      "asset_id": "TYSV001000",
      "ip": "10.0.0.1",
      "machine_type": "M5s",
      "module": "[N][腾讯云边缘可用区]-[现网运营]"
    }
  ],
  "online_count": 15,
  
  "offline_devices": [
    {
      "asset_id": "TYSV001001",
      "ip": "10.0.0.2",
      "machine_type": "M5s",
      "module": "[N][腾讯云边缘可用区]-[待上线]",
      "reason": "模块状态：待上线"
    }
  ],
  "offline_count": 1,
  "non_tez_count": 0,
  
  "from_cache": true,
  "last_sync_at": "2026-05-25T10:30:45.123456",
  
  "message": "虚拟化机位: 20（空闲10/已用8），TEZ已上线15台, 未上线1台"
}
```

#### 响应 (首次登录，需要等待)

```json
{
  "zone": "zone_a",
  "status": "login_required",
  "idc": "宁波边缘二区（移动）",
  "message": "系统首次启动，需要进行身份验证。请查看浏览器窗口...",
  "free_count": null,
  "online_devices": [],
  "offline_devices": []
}
```

#### 响应 (错误 5xx)

```json
{
  "zone": "zone_a",
  "idc": "宁波边缘二区（移动）",
  "message": "查询失败: IDCRM 登录态失效（被踢回 SSO），请重新扫码登录",
  "free_count": null
}
```

---

## 📝 关键配置（settings）

在 `.env` 或 `settings.local.json` 中：

```bash
# 浏览器配置
TEZ_BROWSER_PROFILE_DIR=~/.tez/browser-profile  # Playwright 持久化目录
TEZ_BROWSER_HEADLESS=true                       # 是否无头模式
TEZ_BROWSER_IGNORE_HTTPS_ERRORS=true            # 是否忽略 HTTPS 错误
TEZ_BROWSER_PAGE_TIMEOUT_MS=30000               # 页面加载超时
TEZ_BROWSER_LOGIN_VALID_DAYS=7                  # 登录态有效期（天）

# 数据源 URL
TEZ_IDCRM_BASE_URL=https://idcrm.internal/      # 数全通地址
TEZ_TCUM_BASE_URL=https://tcum.internal/        # TCUM 地址

# 数据源模式
TEZ_IDCRM_MODE=browser                          # browser or mock
TEZ_TCUM_MODE=browser                           # browser or mock

# 数据库
DATABASE_URL=sqlite:///./data/tez.db
```

---

## 🧪 测试用例

### 单元测试文件

```
/tests/test_zone_instance_stats.py     # Zone 实例统计
/tests/test_browser_session.py         # BrowserSession 单例
/tests/test_idcrm_browser.py           # IDCRM 浏览器自动化
/tests/test_tcum_browser.py            # TCUM 浏览器自动化
```

### 常见测试场景

1. **首次查询（无缓存）**
   - Mock IDCRM 返回 10 个虚拟化机位
   - Mock TCUM 返回 8 台 TEZ 设备（6 online, 2 offline）
   - 验证数据库被正确写入

2. **缓存有效期内查询（快速路径）**
   - 第一次查询 → 同步
   - 第二次查询（5 分钟内）→ 返回缓存
   - 验证响应时间 < 10ms

3. **缓存过期重新同步**
   - 数据库中的 `last_sync_at` 设为 8 天前
   - 查询 → 触发同步
   - 验证 `last_sync_at` 被更新

4. **强制刷新**
   - 查询 `?force_refresh=true`
   - 验证忽略缓存，直接同步

5. **登录态失效处理**
   - 删除 Playwright profile
   - 查询 → 返回 "login_required" 状态
   - 模拟用户登录
   - 再次查询 → 成功

---

## 🐛 已知问题与 TODO

### 问题清单

- [ ] **首次登录竞态条件** (已分析，见上文)
  - 原因：SSO 异步，API 不等待
  - 影响：首次查询返回 0
  - 解决方案：主动等待或返回等待状态

- [ ] **IDCRM 页面结构变化** 
  - 风险：CSS 选择器失效
  - 当前值班：自动降级 / 报错

- [ ] **TCUM 状态列展示**
  - 需要自动勾选"机器状态"列
  - 当前实现可能偶发失败

- [ ] **翻页边界情况**
  - IDCRM/TCUM 都支持翻页，但最多查 10 页
  - 超过 100+ 条数据无法采集完整

- [ ] **并发操作锁**
  - BrowserSession 有 `_operation_lock`，但粒度是全局
  - 多个请求会排队，可能导致超时

### TODO 清单

- [ ] 首次登录流程优化（等待机制或进度提示）
- [ ] 支持后台异步同步 (目前是阻塞同步)
- [ ] 添加同步进度监控 WebSocket
- [ ] 支持部分失败时保存部分数据
- [ ] 性能优化：批量查询 TCUM 时支持并发请求
- [ ] IDCRM 真实页面 PoC（W4 联调）

---

## 📚 相关文档

- `docs/15-周边系统集成.md` - PoC 验证报告（TCUM/IDCRM 页面结构）
- `docs/02-周边系统集成.md` - CMDB 表结构、vStation API、云 API 3.0
- `.env.example` - 配置示例
- `alembic/versions/` - 数据库迁移脚本

---

## 🎓 架构设计总结

### 核心思想

1. **本地缓存优先**：99% 的查询走毫秒级的本地数据库，极少数触发云端同步
2. **共享浏览器 Context**：所有自动化脚本共用一个 Playwright context，复用 SSO 登录态
3. **异步操作同步化**：将浏览器的异步操作（加载、SSO）转换为后端的同步 API 响应
4. **容错降级**：任何一个数据源失败，返回缓存或空结果，不完全崩溃

### 性能指标

| 场景 | 响应时间 | 备注 |
|------|----------|------|
| 缓存命中 | < 10ms | 本地 SELECT 查询 |
| 首次同步 | 15-30s | IDCRM 4s + TCUM 8s + DB write |
| IDCRM 单个查询 | 4-8s | 页面加载 + SSO |
| TCUM 批量查询 | 8-12s | 页面加载 + 翻页 |

