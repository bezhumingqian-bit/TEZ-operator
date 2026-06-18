# TEZ Operator — 公共记忆（Shared Memory）

> 从代码库中提炼的跨文件公共知识。
> 
> **作用**：AI 助手进入项目时优先读取，快速理解项目的真实架构约束、设计模式与潜在陷阱。
> **更新方式**：代码发生重大架构变更时，重新运行提炼流程（当前为 AI 手工提炼，未来可脚本化）。

---

## 1. 架构骨架

### 1.1 分层架构（严格）

```
Router  →  Service  →  Client / Model
   ↓          ↓            ↓
Schema    业务逻辑      外部系统 / DB
```

- **Router**：只负责校验（Schema）、调度（调用 Service）、返回响应。禁止直接操作 Model 或 Client。
- **Service**：业务逻辑的唯一场所。HostService 是典型的聚合器模式——汇聚 CMDB + IDCRM + TCUM 三数据源。
- **Client**：外部系统交互。每个上游系统都有 **三态实现**：`mock` | `api` | `browser`。
- **Model**：SQLAlchemy 2.0 ORM，仅用于数据库操作。

> **注意**：`app.routers.hosts` 是路由层中的例外——它除了调用 Service 外，还直接依赖了 `browser_session`、`tcum_browser`、`tcum_http` 等客户端。这是历史遗留或特定需求（如实时浏览器状态检查），新增路由不要效仿。

### 1.2 客户端三态模式（W2 核心设计）

每个上游系统（CMDB / TCUM / IDCRM）都遵循同一套模式：

```
base.py (ClientMode + 异常定义)
  ├── base_browser.py (BaseBrowserImpl) ──→  Playwright 自动化
  ├── base.py (BaseHTTPClient) ───────────→  httpx API 调用
  │
  └── {system}/                     ← 每个系统一个包
      ├── {system}_browser.py       ← BrowserImpl（继承 BaseBrowserImpl）
      ├── {system}_http.py          ← HttpClient（继承 BaseHTTPClient）
      ├── {system}_mock.py          ← MockImpl（固定假数据）
      └── {system}.py               ← Client（工厂，按 mode 分发）
```

**切换方式**：环境变量 `TEZ_{SYSTEM}_MODE` = `mock` | `api` | `browser`。

**当前默认**：三个系统全部默认 `mock`（因为 W2 阶段 API 账号未到位，browser 需要扫码登录）。

### 1.3 浏览器自动化架构

**登录态管理**：
- Playwright 持久化 profile 目录：`data/playwright-profile`（已 `.gitignore`）
- Cookies 文件 mtime 在 `TEZ_BROWSER_LOGIN_VALID_DAYS`（默认 7 天）内视为有效
- iOA 鉴权要求可视化扫码 → `browser_headless` 默认 `false`

**BaseBrowserImpl 骨架**：
- `_fetch_rows(url)`：打开页面 → SSO 自动点击 → 提取表格行数据
- `_try_finish_sso_flow(page)`：在 SSO 页自动点"登录/确认/继续/授权"等按钮，轮询 120 秒
- `_safe_cell(cells, idx)`：安全取单元格，空值/`-` 返回 `None`
- `_normalize_status(raw)`：委托到 `app.utils.normalize`
- `SELECTOR_FALLBACKS`：表格选择器兜底链（`.tea-table` → `.ant-table-row` → `table tbody tr`）

**异常处理**：
- `BrowserAuthExpired`：被踢回 SSO 登录页时抛出。上层应当：
  1. 记录日志 + 企微告警（`TEZ_WECOM_WEBHOOK`）
  2. 当前请求降级返回（HostService 会标记 `partial=True`）
  3. 通知用户重新扫码登录

---

## 2. 单一来源（Single Source of Truth）

以下模块的约束是**全局硬规则**，任何修改必须先改这些文件：

| 模块 | 职责 | 违规后果 |
|------|------|---------|
| `app.utils.normalize` | 状态归一化：任意 status → `online/offline/maintenance` | 状态不一致、统计错误 |
| `app.utils.device_classifier` | TEZ 设备分类：`is_tez`, `is_transitional`, `reason` | 边缘区设备误判 |
| `app.config.Settings` | 所有环境变量配置的唯一来源，前缀 `TEZ_` | 配置散落、安全泄露 |
| `app.models.base.Base` | ORM 基类 + Alembic 命名约定 | 迁移命名混乱 |
| `app.clients.base_browser.BaseBrowserImpl` | 浏览器自动化公共逻辑 | SSO、表格提取逻辑重复 |
| `app.clients.base.BaseHTTPClient` | HTTP 请求公共逻辑（重试、日志脱敏） | token 泄露、重试策略不一致 |

### 2.1 状态归一化细节

```python
# 中文 → 英文 映射（禁止在别处重复定义）
STATUS_MAP_CN_TO_EN = {
    "运营中": "online",
    "在线": "online",
    "维护中": "maintenance",
    "维修中": "maintenance",
    "待运营": "maintenance",
    "待上线": "maintenance",
    "故障": "offline",
    "离线": "offline",
    "下线": "offline",
}
```

输入示例：`--->运营中[需告警]` → 清洗后 → `online`。
未知状态会打 warning 并返回 `None`。

### 2.2 设备分类细节

判定优先级：
1. 模块含 `腾讯云边缘可用区` 或 `TEZ` → **是 TEZ**
2. 模块含 `边缘计算` + 过渡关键词（待上线/上线中/搬迁/buffer/未上线）→ **是 TEZ（过渡中）**
3. 其他 → **非 TEZ**

---

## 3. 关键数据流与契约

### 3.1 Host 查询主链路

```
GET /api/v1/hosts/{asset_id}
  ↓
routers.hosts
  ↓
HostService.get_host(asset_id)
  ├── CMDBClient(mode?) ──→ CMDBBrowserImpl / CMDBMockImpl
  ├── IDCRMClient(mode?) ──→ IDCRM...Impl ──→ 机柜位置
  └── TCUMClient(mode?) ───→ TCUM...Impl
  ↓
合并三源数据 → HostInfo（partial 标记缺失源）
```

**HostInfo 的 `meta` 字段**：
- `data_sources`: 哪些数据源返回了数据
- `errors`: 各数据源的异常信息
- `from_cache`: 是否来自缓存
- `partial`: 是否为部分数据（某数据源失败但其他成功）

### 3.2 Zone 资源概览链路

```
GET /api/v1/zones/{zone}/overview
  ↓
ZoneResourceService.get_zone_overview(zone)
  ├── CMDB ──→ 实例统计（按客户/机型分组）
  ├── IDCRM ──→ 机架位占用情况
  └── TCUM ──→ 边缘可用区详情
  ↓
ZoneSnapshot（入库 + 缓存）
```

### 3.3 工单（WorkOrder）链路

```
POST /api/v1/workorders
  ↓
WorkOrderService.create_order()
  ├── DB: 写入 workorder + op_log
  └── 异步: 推送到腾讯文档（TEZ_TENCENT_DOC_URL）
```

**腾讯文档推送失败处理**：
- 启动时 `WorkOrderService.retry_pending_pushes()` 自动重试未完成的推送
- 工单状态流转通过 `transition()` 方法，自动记录 `WorkOrderLog`

### 3.4 联系人路由（Contact Routing）

```
GET /api/v1/contacts/route?q=xxx
  ↓
ContactService.route(query)
  ↓
按 Category 匹配 → 返回 primary / backup / escalation 三级联系人
```

---

## 4. 依赖注入与生命周期

### 4.1 单例管理（`app.deps`）

| 对象 | 作用域 | 说明 |
|------|--------|------|
| `HostService` | 全局单例 | 内部持有 CMDB/IDCRM/TCUM 三个 client 实例 |
| `AsyncEngine` | 全局单例 | 根据 `TEZ_DATABASE_URL` 自动适配：sqlite→aiosqlite, pymysql→aiomysql |
| `AsyncSession` | 请求级 | 每请求一个 session，请求结束自动关闭 |

**测试覆盖**：`set_host_service(None)` 可重置单例，用于测试 mock。

### 4.2 应用生命周期（`lifespan`）

```
启动：
  1. Redis ping（失败 warn，cache 降级到内存）
  2. DB ping（失败 warn）
  3. 浏览器登录态预检（仅日志）
  4. 启动定时任务（scheduler）
  5. 重试未完成的腾讯文档推送

关闭：
  1. 停止定时任务
  2. 关闭 HostService（关闭内部 clients）
  3. 关闭 CacheService（关闭 Redis pool）
  4. 关闭 BrowserSession（关闭 Playwright context）
```

---

## 5. 缓存策略

### 5.1 CacheService 架构

```
CacheService
  ├── Redis（首选）
  └── _MemoryCache（降级，进程内 dict + TTL）
```

**降级触发条件**：Redis 连接失败（未启动或网络异常）。

### 5.2 TTL 配置（`app.config`）

| 数据类型 | TTL | 配置项 |
|---------|-----|--------|
| 主机详情 | 300s | `cache_default_ttl` |
| Zone 列表 | 600s | `cache_zone_ttl` |

### 5.3 已知陷阱

> **本地未启动 Redis 时，`test_list_zones` 相关测试可能失败**
> 
> 原因：缓存降级到内存缓存后返回真实数据，导致断言不匹配。
> 解决：`docker compose up -d redis`

---

## 6. 安全红线（代码级体现）

| 规则 | 代码中的体现 |
|------|-------------|
| JWT Secret 必须从环境变量读取 | `config.py: jwt_secret_key` 默认空字符串，生产必须设置 |
| Password Salt 必须从环境变量读取 | `config.py: password_salt` 默认空字符串，生产必须设置 |
| 禁止日志打印 token | `BaseHTTPClient.request()` 只打 path/method，不打 headers |
| SQL 必须参数化 | 全项目使用 SQLAlchemy ORM，无手写 SQL（除启动自检 `SELECT 1`） |
| 敏感 URL/Token 禁止硬编码 | `tencent_doc_url`, `cmdb_base_url` 等全部走 `TEZ_*` 环境变量 |

---

## 7. ORM 与数据库

### 7.1 模型基类

所有模型继承 `Base` + 可选 `TimestampMixin`：

```python
class MyModel(Base, TimestampMixin):
    # created_at / updated_at 自动由 TimestampMixin 提供
```

### 7.2 Alembic 命名约定（在 `Base` 中定义）

```python
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
```

---

## 8. 批量查询限流（W3 防御性设计）

```python
# app.config.Settings
batch_concurrency: int = 5   # 并发查询上限
batch_max_size: int = 100    # 单次请求最大条数
```

HostService 的 `batch_get_hosts` / `batch_get_hosts_mixed` 内部应当遵守此限制，防止瞬间打开过多浏览器 tab 或 HTTP 连接。

---

## 9. 模块间的"规范漂移"风险点

> 以下代码位置与 AGENTS.md 规范存在偏差或需要特别关注：

| 位置 | 现象 | 建议 |
|------|------|------|
| `app.routers.hosts` | 直接 import 多个 client（`tcum_browser`, `idcrm_http` 等），违反"router 不准直接操作 client" | 评估是否应下沉到 HostService 或 ZoneResourceService |
| `app.clients.base` | `BrowserAuthExpired` 类名以 `Error` 结尾而非 `Exception`，注释说明是"任务包指定的命名" | 保留，不要按常规 Python 惯例重命名 |

---

## 10. 常用扩展路径

当需要新增一个上游系统（如新的 CMDB 替代方案）时，标准步骤：

1. **定义接口抽象**：`app/clients/new_sys.py` 中定义 `NewSysAPIImpl`（抽象基类）
2. **实现三态**：
   - `new_sys_browser.py` 继承 `BaseBrowserImpl`
   - `new_sys_http.py` 继承 `BaseHTTPClient`
   - `new_sys_mock.py` 返回固定假数据
3. **工厂分发**：`new_sys.py` 中的 `NewSysClient` 按 `TEZ_NEWSYS_MODE` 选择实现
4. **接入 Service**：在 `HostService` 或新建 Service 中引入 `NewSysClient`
5. **注册路由**：在 `app/main.py` 中注册新 router（如果需要新 API）
6. **更新配置**：`app/config.py` 中添加 `newsys_mode`, `newsys_base_url` 等字段
7. **更新公共记忆**：更新本文件，记录新的数据源契约

---

## 11. AI 协作核心原则 — 反向约束驱动

> **来源**：CVM 团队 CVM-Bench 评测（20 个真实需求 + 300+ 轮测试），GLM-5.1 + 约束规则追平 Claude Opus 4.6。
> **核心结论**：需求写法对准确率的影响，远大于换模型。

### 11.1 反向约束优先（最重要的一条）

**"一句反向约束 > 一大段正向描述"** — 模型最大的问题往往不是不会写代码，而是按它熟悉的套路"补"了不该有的东西。

真实数据：实例巨帧 MTU 需求，只加了一句"**不引入限流、流控、熔断逻辑**"，编码分从 **19.8 → 76.8**。

**精确锚定原则**（来源：Claude Code 泄露源码的 Prompt 工程）：

| 原则 | 示例 |
|------|------|
| 用具体数字代替模糊描述 | "3 行相似的代码 > 一次过早的抽象"（而非"别过度抽象"） |
| 不为一件事建工厂 | "不为一次性操作创建辅助工具或抽象"（而非"别建多余的类"） |
| 不多写一行 | "不为你没修改的代码添加 docstring/注释"（而非"别写多余文档"） |
| 不防御不可能 | "不为不可能发生的场景添加错误处理"（而非"别过度防御"） |
| 及时清理 | "创建的临时文件/脚本在任务结束时清理删除" |

**在给出 AI 任务时，必须首先明确"哪些不做"：**

- ❌ 不引入限流、流控、熔断
- ❌ 不修改已有接口的签名
- ❌ 不重构与该需求无关的代码
- ❌ 不新增依赖（或明确哪些包可以用）
- ❌ 不改变现有数据库 schema（或明确允许改动范围）

### 11.2 需求必须有这 5 类信息

| 维度 | 要回答的问题 | 不好 vs 好的例子 |
|------|------------|-----------------|
| **背景** | 为什么要做？性能/稳定性/业务规则变化？ | "支持可用区机型维度熔断" → "当前熔断是全局的，需要按可用区+机型维度独立熔断" |
| **范围** | 涉及哪些服务、仓库、接口、流程？ | 只说"优化查询" → "改动限于 HostService.get_host() 链路的三个查询事件" |
| **反向约束** | **哪些方向明确不做？** 哪些旧逻辑绝不能动？ | "批量优化" → "性能问题通过批量查询本身解决，**不引入限流/流控/熔断**" |
| **不可推导信息** | 命名约定、枚举值、协议格式、接口字段大小写 | 写出 "ResourcePoolPack"而非"ResourcePool"，模型猜不到 |
| **验收标准** | 怎么判断写对了？必须覆盖的测试场景？ | "实现后跑 `pytest tests/test_hosts.py -v` 全部通过" |

### 11.3 需求不清晰时，AI 必须先问再写

最危险的 AI 行为：**不确定的地方也不问，直接猜**。直接猜的结果通常 50 分以下。

**指令模板**（写进 prompt/system prompt 里）：

> 如果需求中存在多种合理解释，先列出所有理解并标注差异，等我确认后再开始写代码。不要自行选择一种假设。

以下场景**必须触发提问**：
- 需求中出现"支持/兼容/优化"但没有具体范围
- 有多个现有接口看起来都能复用
- 命名/协议/枚举来自外部系统，代码里查不到
- 改动跨多个服务，调用链不完整

如果确实无人回答，也至少让 AI **先列出所有假设**再动手。这样错误暴露在设计阶段，而不是藏进代码。

### 11.4 复杂需求必须拆解

一次性编码通过率随复杂度**瀑布式下降**：

| 难度 | 范围 | 一次性通过率 |
|------|------|:---:|
| 低 | 1 仓库，1-4 文件 | 95% |
| 中 | 1-3 仓库 | 60-75% |
| 高 | 3-4 仓库 | <60% |
| 困难 | 7 仓库，千行改动 | 几乎全盘错 |

**规则**：跨 3 个及以上仓库的需求，必须拆成独立子任务，每个子任务单独设计→编码→验证。

### 11.5 给 AI 派开发任务的清单模板

```
【目标】
<一句话：这次到底解决什么问题？>

【范围】
涉及服务：<列全>
涉及仓库/模块：<列全>
涉及接口/流程：<列全>

【反向约束】（最重要）
- 不做的：<逐条列出>
- 旧逻辑不能动的：<逐条列出>

【命名/协议约定】
- 固定命名：
- 枚举值：
- 接口字段格式（大小写/类型）：

【验收标准】
- <如何验证写对了>
- <必须覆盖的测试>
```

---

*Last updated: 2026-06-18 — 新增 §11 AI 协作核心原则、§12 Claude Code 源码模式*
*Sources: AGENTS.md, .kimi/code-context/, app/config.py, app/clients/base*.py, app/main.py, app/deps.py, app/utils/*, KM article #663040 (CVM-Bench), Claude Code leaked source (03/2026)

---

## 12. Claude Code 源码模式 (2026-03 泄露)

> 来自 Anthropic 意外泄露的 512,000 行 Claude Code CLI 源码。以下模式可直接融入 TEZ Operator 工程实践。

### 12.1 Dream Memory（梦境记忆系统）

Claude Code 的内存系统分 4 阶段将零散对话沉淀为结构化知识：

| 阶段 | 内容 | TEZ Operator 对应 |
|------|------|------------------|
| 碎片收集 | 获取近期对话片段、代码变更、用户反馈 | 每次对话完成后，AI 自动扫描本次改动的关键决策 |
| 关联分析 | 找出碎片间的内在联系（如过去的配置问题与当前报错关联为同一根因） | 更新 shared_memory 时检查是否与已有条目矛盾或重复 |
| 知识萃取 | 将碎片提炼为高价值、可复用的知识点 | 写入 shared_memory.md 时用精炼的表格/规则形式，而非长篇叙述 |
| 记忆索引 | 存入向量库供后续检索 | shared_memory.md 即索引，每次进入项目必读 |

更新触发规则（在 AGENTS.md §8.6 基础上强化）：
- AI 完成任务后，不止检查"是否需要更新"，而是主动问"通过这次修改，我学到了什么新规则？"
- 同一问题被修正 2 次以上 → 必须写入 shared_memory 作为反模式

### 12.2 System Prompt 静态/动态分离

Claude Code 的 System Prompt 分两层：

| 层 | 内容 | 缓存策略 | TEZ 启示 |
|----|------|---------|---------|
| 静态层 | 身份定义、安全指令、操作安全性、风格要求 | 全局缓存（所有用户共享） | 写入 AGENTS.md（每次会话固定加载） |
| 动态层 | CLAUDE.md 内容、环境信息、MCP 指令、工具结果提示 | 每次会话重算 | 写入 .kimi/shared_memory.md（每次进入项目时加载） |

关键设计：UserContext（CLAUDE.md 内容）不作为 system prompt，而是包裹在 `<system-reminder>` 标签中作为第一条用户消息注入。好处：System prompt 保持稳定以利用缓存，`<system-reminder>` 提供足够上下文信号。

TEZ Operator 的应用：`app/services/agent.py` 中的 AI Agent system prompt 构建可参考此模式——静态部分（身份+规则）固定，动态部分（用户上下文+环境）每次注入。

### 12.3 工具最小权限（disallowedTools）

Claude Code 的每个 Agent 都有 `disallowedTools` 明确列出禁止操作：

| Agent | 禁止操作 |
|-------|---------|
| Explore Agent | 禁止 Write、Edit、rm、mv、cp、touch、Agent 嵌套 |
| Plan Agent | 同上，禁止文件修改 |
| Verification Agent | 同上，禁止修改被测试代码 |

设计原则：默认最小权限。新 Agent 的 `isConcurrencySafe` 和 `isReadOnly` 默认 `false`——忘记覆盖时采取最保守策略。

TEZ Operator 应用：tez-ops 团队中已区分角色（developer/reviewer/qa），后续若新增子 Agent，应显式声明禁止工具列表。

### 12.4 "不做什么" Prompt 精确锚定

Claude Code 泄露源码中的实际 Prompt 片段（已融入 §11.1）：

```
Don't add features, refactor code, or make "improvements" beyond what was asked.
Don't add error handling, fallbacks, or validation for scenarios that can't happen.
Don't create helpers, utilities, or abstractions for one-time operations.
Three similar lines of code is better than a premature abstraction.
If you created temporary files, scripts, or helper files for iteration,
  clean them up when the task is finished.
```
