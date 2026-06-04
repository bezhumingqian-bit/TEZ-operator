# TEZ Operator - "节点资源概况"功能 代码地图

## 🎯 快速导航

### 问题根源
**首次登录时竞态条件导致返回结果为 0**
- 根本原因：浏览器 SSO 登录异步，API 不等待就返回空结果
- 详细分析见：`ANALYSIS_NODE_OVERVIEW.md` § 问题根源

---

## 📂 前端代码

### 主要组件

| 文件 | 行数 | 功能 | 关键函数 |
|------|------|------|---------|
| `/web/src/views/HostSearch.vue` | L209-302 | 节点资源概况 Tab | `fetchNodeOverview()` |
| `/web/src/api/hosts.ts` | 全文 | API 客户端 | `listZones()` |
| `/web/src/types/host.ts` | 全文 | TypeScript 类型 | `NodeOverviewData` |

### 前端关键代码片段

#### HostSearch.vue 中的"节点资源概况" Tab
```vue
<!-- 行 209-302 -->
<el-tab-pane label="节点资源概况" name="node_overview">
  <!-- 下拉选择 Zone + 查询按钮 -->
  <el-select v-model="nodeZoneSelected" ... />
  <el-button @click="onNodeOverview()">查询资源概况</el-button>
  <el-button @click="onNodeForceRefresh()">🔄 强制刷新</el-button>
  
  <!-- 结果展示 -->
  <el-card><template #header><b>空闲虚拟化机位</b></template>
    {{ nodeOverviewData.positions.message }}
  </el-card>
  
  <el-card><template #header><b>已上线设备</b></template>
    <el-table :data="nodeOverviewData.online_devices" ... />
  </el-card>
  
  <el-card><template #header><b>未上线设备</b></template>
    <el-table :data="nodeOverviewData.offline_devices" ... />
  </el-card>
</el-tab-pane>
```

#### 关键函数：fetchNodeOverview
```typescript
// 行 487-507
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
      message: resp.message || '',
    },
    offline_devices: resp.offline_devices || [],
    online_devices: resp.online_devices || [],
    from_cache: resp.from_cache,
    last_sync_at: resp.last_sync_at,
  }
}
```

---

## 🔧 后端代码

### 核心文件

| 文件 | 行数 | 功能 | 关键方法 |
|------|------|------|---------|
| `/app/routers/hosts.py` | L434-452 | API 路由 | `get_zone_overview()` |
| `/app/services/zone_resource_service.py` | 全文 | 业务逻辑 | `get_zone_overview()` |
| `/app/skills/idcrm_position_skill.py` | 全文 | IDCRM 自动化 | `query_free_positions()` |
| `/app/clients/tcum_browser.py` | 全文 | TCUM 自动化 | `batch_search()` |
| `/app/clients/browser_session.py` | 全文 | 浏览器单例 | `BrowserSession` |
| `/app/models/zone_snapshot.py` | 全文 | 数据模型 | `ZoneSnapshot`, `ZoneDevice` |

### API 端点

#### GET /api/v1/zones/{zone}/overview

**源代码**：`/app/routers/hosts.py` L434-452

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
    from app.services.zone_resource_service import ZoneResourceService
    svc = ZoneResourceService(session)
    return await svc.get_zone_overview(zone, force_refresh=force_refresh)
```

**参数**:
- `zone` (string, required): 可用区名称，如 `zone_a`, `ap-sh-2-2`
- `force_refresh` (boolean, optional, default=false): 强制从云端刷新

**返回示例**:
```json
{
  "zone": "zone_a",
  "idc": "宁波边缘二区（移动）",
  "total_positions": 20,
  "free_count": 10,
  "used_count": 8,
  "online_devices": [...],
  "offline_devices": [...],
  "from_cache": true,
  "last_sync_at": "2026-05-25T10:30:45.123456",
  "message": "虚拟化机位: 20（空闲10/已用8），TEZ已上线15台, 未上线1台"
}
```

### Service 业务逻辑

#### ZoneResourceService.get_zone_overview()

**源代码**：`/app/services/zone_resource_service.py` L32-66

**执行流程**:
```
1. 读本地数据库 → snapshot = await _get_snapshot(zone)
   
2. 检查有效期（7 天）
   ├─ 未过期 → 返回缓存（毫秒级）
   └─ 过期或无数据 → 进入同步流程
   
3. 从云端同步 → result = await _sync_from_cloud(zone)
   ├─ IDCRM 查虚拟化机位 + 设备固资号
   ├─ TCUM 批量查设备状态
   ├─ 数据库 Upsert ZoneSnapshot + ZoneDevice
   └─ 返回新数据
   
4. 同步失败处理
   ├─ 若有旧缓存 → 返回旧数据 + 警告
   └─ 无任何数据 → 返回错误
```

#### 关键内部方法

```python
# 从云端采集数据
async def _sync_from_cloud(self, zone: str) -> dict[str, Any] | None

# 保存到本地库
async def _save_snapshot(self, zone, idc, pos_result, online_devices, offline_devices, ...)

# 组装响应
def _build_response(self, snapshot, devices, from_cache)
```

### 浏览器自动化

#### IDCRMPositionSkill - 数全通机位查询

**源代码**：`/app/skills/idcrm_position_skill.py`

**关键参数**:
```python
WAIT_AFTER_GOTO = 4  # 页面加载后等待 4 秒
WAIT_AFTER_FILTER = 8  # 查询后等待 8 秒
MAX_RETRY = 2  # 校验失败最多重试
```

**主要方法**:
```python
async def query_free_positions(self, idc: str) -> dict[str, Any]
```

**SOP**:
1. 打开 IDCRM 页面：`/db/positions`
2. 等待页面加载 + SSO 流程（4 秒）
3. ⚠️  **检查登录态**：`if is_login_url(page.url) → 返回错误`
4. 勾选"机位放置设备(服务器)"列
5. 设置分页为 100 条/页
6. 填筛选条件：
   - 机位逻辑区域 = "通用虚拟化bonding区"
   - 机房管理单元 = {idc}
7. 点"查询"按钮
8. 翻页提取全部结果
9. 统计各状态 + 提取机位上的固资号

**返回数据**:
```python
{
    "total_positions": int,      # 虚拟化机位总数
    "free_count": int,           # 空闲机位
    "used_count": int,           # 已用机位
    "other_count": int,          # 其他状态
    "all_assets": [str],         # 所有机位上的设备固资号
    "message": str,
}
```

**问题点**（首次登录）:
- L64-65：检查登录态
  ```python
  if is_login_url(page.url):
      return {"free_count": None, "message": "数全通登录态失效，请扫码登录"}
  ```
- 此时 cookies 文件可能还没被写入 → 返回错误

#### TCUMBrowserImpl - TCUM 设备状态查询

**源代码**：`/app/clients/tcum_browser.py`

**关键方法**:
```python
async def batch_search(self, asset_ids: list[str]) -> list[dict[str, Any]]
```

**功能**:
- 输入多个固资号（用`;`拼接）
- 一次查询获取所有设备状态
- 支持翻页（最多 10 页，每页 50 条）
- 自动勾选"机器状态"列
- 处理 SSO 中转流程

**返回字段** (每条设备):
```python
{
    "asset_id": str,             # 固资号
    "ip": str,                   # IP
    "machine_type": str,         # 机型
    "module": str,               # 模块路径
    "status": "online" | "offline" | "maintenance",  # 标准化状态
    "_source": "tcum-browser",
}
```

**重要细节**:
- L92-101：等待渲染 + 尝试完成 SSO 中转
- L157-201：勾选"机器状态"列
- L387-436：解析行数据（PoC 已验证 12 列顺序）
- 状态中英文映射（L350-384）：
  ```python
  "运营中" → "online"
  "维护中" → "maintenance"
  "离线" → "offline"
  ```

#### BrowserSession 单例

**源代码**：`/app/clients/browser_session.py`

**设计要点**:
- **全局单例**：所有自动化脚本共用 1 个 BrowserContext
- **共享登录态**：通过 `new_page()` 复用同一个 session 的 cookies
- **持久化**：
  ```python
  launch_persistent_context(
      user_data_dir=~/.tez/browser-profile,
      headless=True,
      ignore_https_errors=True,
  )
  ```
- **登录态检查**:
  ```python
  @staticmethod
  def is_login_valid() -> bool:
      cookies_file = profile_dir / "Default" / "Cookies"
      if not cookies_file.exists():
          return False  # 首次需要扫码
      age_days = (time.time() - mtime) / 86400
      return age_days < 7  # 默认 7 天有效
  ```

**关键方法**:
```python
@classmethod
@asynccontextmanager
async def page(cls) -> AsyncIterator:
    """打开新 page，用完自动关闭"""
    async with cls._operation_lock:  # ⚠️ 全局锁
        ctx = await cls._ensure()
        page = await ctx.new_page()
        try:
            yield page
        finally:
            await page.close()
```

### 数据模型

#### ZoneSnapshot 表

**源代码**：`/app/models/zone_snapshot.py` L20-45

```python
class ZoneSnapshot(Base, TimestampMixin):
    zone: str (PK)                      # 可用区名
    idc: str                            # 机房名
    total_positions: int                # 虚拟化机位总数
    free_count: int                     # 空闲机位
    used_count: int                     # 已用机位
    other_count: int                    # 其他状态
    online_count: int                   # 已上线设备数
    offline_count: int                  # 未上线设备数
    non_tez_count: int                  # 非 TEZ 设备数
    last_sync_at: datetime              # ⚠️ 上次同步时间（过期检查用）
    raw_data: dict (JSON)               # 原始采集结果备份
```

#### ZoneDevice 表

**源代码**：`/app/models/zone_snapshot.py` L47-62

```python
class ZoneDevice(Base, TimestampMixin):
    id: int (PK, autoincrement)
    zone: str (indexed)                 # 所属可用区
    asset_id: str (indexed)             # 固资号
    ip: str                             # IP
    machine_type: str                   # 机型
    module: str                         # 模块
    status: str                         # 设备状态
    category: str                       # "online" / "offline" / "non_tez"
    is_tez: bool                        # 是否 TEZ 设备
    reason: str                         # 未上线原因
```

---

## ⚠️ 首次登录竞态条件问题

### 问题发生的位置

| 文件 | 行 | 代码 | 问题 |
|------|-----|------|------|
| `/app/clients/tcum_browser.py` | L59-63 | `if not BrowserSession.is_login_valid()` | 仅记录日志，继续执行 |
| `/app/skills/idcrm_position_skill.py` | L64-65 | `if is_login_url(page.url)` | 4 秒等待可能不够 |
| `/app/clients/browser_session.py` | L118-137 | `is_login_valid()` | 检查 cookies mtime |

### 时间线

```
T+0ms:    用户首次访问 → 浏览器弹出 SSO 登录窗口
T+1500ms: 用户点"查询资源概况" → 前端发起 API 请求
T+2000ms: 后端触发 IDCRM 自动化
          ├─ Playwright 启动页面
          ├─ 访问 IDCRM，获得登录页
          ├─ 等待 4 秒（不够！）
          ├─ 检查登录态 → False（cookies 还没写入）
          └─ 返回 free_count=0
T+5000ms: 用户完成扫码 → cookies 文件被写入
T+3000ms: 前端收到 API 响应 ❌ free_count=0

用户刷新后重新查询
T+5500ms: 此时 cookies 有效 ✅ 正确数据
```

### 改进方案

见 `ANALYSIS_NODE_OVERVIEW.md` § 设计问题与改进方案

---

## 🔍 关键配置

### 环境变量

**文件**：`.env` 或 `settings.local.json`

```bash
# 浏览器
TEZ_BROWSER_PROFILE_DIR=~/.tez/browser-profile
TEZ_BROWSER_HEADLESS=true
TEZ_BROWSER_PAGE_TIMEOUT_MS=30000
TEZ_BROWSER_LOGIN_VALID_DAYS=7

# 数据源
TEZ_IDCRM_BASE_URL=https://idcrm.internal/
TEZ_TCUM_BASE_URL=https://tcum.internal/
TEZ_IDCRM_MODE=browser  # or mock
TEZ_TCUM_MODE=browser   # or mock

# 数据库
DATABASE_URL=sqlite:///./data/tez.db
```

### 常数定义

| 常数 | 值 | 位置 | 说明 |
|------|-----|------|------|
| `SYNC_EXPIRE_DAYS` | 7 | zone_resource_service.py L23 | 缓存有效期 |
| `WAIT_AFTER_GOTO` | 4 | idcrm_position_skill.py L34 | IDCRM 页面加载等待 |
| `WAIT_AFTER_FILTER` | 8 | idcrm_position_skill.py L35 | IDCRM 查询后等待 |
| `MAX_RETRY` | 2 | idcrm_position_skill.py L46 | IDCRM 校验失败重试 |
| `DEFAULT_WAIT_AFTER_GOTO_MS` | 3500 | tcum_browser.py L47 | TCUM 页面加载等待 |

---

## 📊 性能指标

| 场景 | 时间 | 位置 | 说明 |
|------|------|------|------|
| 缓存命中 | < 10ms | zone_resource_service.py L46-50 | SELECT 查询 |
| IDCRM 采集 | 4-8s | idcrm_position_skill.py L34-35 | 页面加载 + SSO |
| TCUM 采集 | 8-12s | tcum_browser.py L47, L92-101 | 页面加载 + 翻页 |
| 首次同步 | 15-30s | - | 两个数据源 + DB 写入 |

---

## 🧪 测试

**测试文件**:
- `/tests/test_zone_instance_stats.py` - Zone 实例统计
- `/tests/test_browser_session.py` - BrowserSession 单例
- `/tests/test_tcum_browser.py` - TCUM 浏览器自动化
- `/tests/test_idcrm_browser.py` - IDCRM 浏览器自动化（框架占位）

---

## 📝 数据库迁移

**Alembic 版本**：`/alembic/versions/`

查看 `zone_snapshots` 和 `zone_devices` 表的创建脚本。

---

## 🔗 相关文档

- `ANALYSIS_NODE_OVERVIEW.md` - 完整详细分析（本文档的来源）
- `docs/15-周边系统集成.md` - PoC 验证报告
- `docs/02-周边系统集成.md` - CMDB/vStation API
- `.env.example` - 配置示例

---

## 📌 快速参考

### 添加新的可用区

1. 编辑 `/app/data/zone_mapping.py` 中的 `ZONE_IDC_MAPPING`
2. 运行数据库迁移（如果需要）
3. 前端会自动从 `/api/v1/zones` 加载新的 zone

### 调整缓存有效期

编辑 `/app/services/zone_resource_service.py` L23:
```python
SYNC_EXPIRE_DAYS = 7  # 改为其他值
```

### 调整页面加载等待时间

编辑 `/app/skills/idcrm_position_skill.py` L34-35:
```python
WAIT_AFTER_GOTO = 4  # IDCRM
WAIT_AFTER_FILTER = 8  # IDCRM 查询后
```

编辑 `/app/clients/tcum_browser.py` L47:
```python
DEFAULT_WAIT_AFTER_GOTO_MS = 3500  # TCUM
```

### 调试 Playwright 页面加载

启用有头模式和日志：
```bash
export TEZ_BROWSER_HEADLESS=false
export LOG_LEVEL=DEBUG
python -m pytest tests/test_tcum_browser.py -vvs
```

---

## ✅ 检查清单

- [ ] 理解首次登录竞态条件问题
- [ ] 理解本地缓存 + 异步同步的设计
- [ ] 理解 Playwright BrowserSession 单例如何共享登录态
- [ ] 了解 IDCRM 和 TCUM 的采集 SOP
- [ ] 理解 zone_snapshots + zone_devices 的数据模型
- [ ] 测试首次查询、缓存命中、强制刷新三种场景

