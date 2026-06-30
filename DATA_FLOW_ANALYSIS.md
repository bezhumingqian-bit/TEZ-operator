# TEZ Operator — 数据流向全貌分析

> 从内部（本机）和外部（第三方平台）两个维度，分析整个系统的数据流向。

---

## 一、架构总览

```
┌─────────────────────────────────────────────────────────────────────┐
│                        本机（docker-compose）                        │
│                                                                      │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐        │
│  │ 用户浏览器│──→│  nginx   │──→│ FastAPI  │──→│  MySQL   │        │
│  │  :80     │   │  :8080   │   │  :8000   │   │  :3306   │        │
│  └──────────┘   └──────────┘   └────┬─────┘   └──────────┘        │
│                                     │                               │
│  ┌──────────┐   ┌──────────┐   ┌───┴──────┐   ┌──────────┐        │
│  │  Redis   │   │Playwright│   │APScheduler│   │  Vue SPA │        │
│  │  :6379   │   │ 进程内   │   │  进程内   │   │  静态文件 │        │
│  └──────────┘   └────┬─────┘   └──────────┘   └──────────┘        │
│                      │                                              │
└──────────────────────┼──────────────────────────────────────────────┘
                       │ 网络请求（内网）
         ┌─────────────┼─────────────┬──────────────┐
         │             │             │              │
    ┌────┴────┐  ┌────┴────┐  ┌─────┴─────┐  ┌────┴────┐
    │  CMDB   │  │  TCUM   │  │  IDCRM    │  │ YunXiao │
    │ 内网平台 │  │ 内网平台 │  │ 数全通平台│  │ 云霄平台 │
    └─────────┘  └─────────┘  └───────────┘  └─────────┘
    
    ┌──────────┐  ┌──────────┐
    │ 腾讯文档  │  │ 企业微信  │
    │(OnePage) │  │(智能机器人)│
    └──────────┘  └──────────┘
```

---

## 二、内部组件（本机部署）

| 组件 | 技术栈 | 端口 | 用途 |
|------|--------|------|------|
| **FastAPI 后端** | Python / FastAPI | `0.0.0.0:8000` | 核心业务逻辑，11 个 router 模块，5 个 service 层 |
| **Vue SPA 前端** | Vue 3 + Element Plus | 静态文件 | 由 FastAPI 静态文件托管，nginx 反代 |
| **MySQL** | MySQL 8.0 | `127.0.0.1:3306` | 持久化数据库，存储所有业务数据 |
| **Redis** | Redis 7-alpine | `127.0.0.1:6379` | 内存缓存（host 详情/zone 列表/幂等键/版本号） |
| **Playwright 浏览器** | Chromium + 持久化 profile | 进程内 | 自动化浏览器，访问 SSO 保护的内网平台 |
| **APScheduler** | AsyncIOScheduler | 进程内 | 定时任务调度（zone 数据同步等） |
| **Agent-Guard** | 自定义中间件框架 | 进程内 | 全局请求拦截 + AI Actor 识别 + Guard 链执行 |

---

## 三、外部平台（需要通过网络获取数据）

### 3.1 四大核心数据源

| 外部平台 | URL | 对接模式 | 状态 |
|----------|-----|---------|------|
| **CMDB** | `cmdb.woa.com` | mock / browser / api(占位) | browser 可用 |
| **TCUM** | `tcum.woa.com` | mock / browser / http / api(占位) | browser + http 可用 |
| **IDCRM**（数全通）| `idcrm.woa.com` | mock / browser / http / api(占位) | browser + http 可用 |
| **YunXiao**（云霄）| `yunxiao.vstation.woa.com` | mock / api / browser | api 可用（headless 稳定） |

### 3.2 业务协同平台

| 外部平台 | URL | 用途 | 对接方式 |
|----------|-----|------|---------|
| **腾讯文档** | `doc.weixin.qq.com` | OnePage 在线表格，工单数据推送 | browser（TencentDocSkill） |
| **企业微信** | Webhook + WebSocket | 智能机器人：消息接收 → 意图路由 → 回复 | webhook 回调 + WS 长连接 |

---

## 四、数据流向详细分析

### 4.1 主机查询流程（核心路径）

```
用户输入固资号/IP
       │
       ▼
┌─────────────────┐
│  Vue 前端       │  →  POST /api/v1/hosts/search
└─────────────────┘
       │
       ▼
┌─────────────────┐
│  FastAPI Router │  →  HostService.get_host()
│  (hosts.py)     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  HostService    │  →  并行调用 3 个 client
│  (聚合编排层)   │
└──┬──────┬───────┘
   │      │      │
   ▼      ▼      ▼
┌────┐ ┌────┐ ┌─────┐
│CMDB│ │TCUM│ │IDCRM│      ← 外部平台（通过 Playwright 浏览器抓取）
└────┘ └────┘ └─────┘
   │      │      │
   └──────┼──────┘
          ▼
   ┌─────────────┐
   │  聚合结果    │
   │  {           │
   │    cmdb: {}, │
   │    tcum: {}, │
   │    idcrm: {} │
   │  }           │
   └──────┬──────┘
          ▼
   ┌─────────────┐
   │ Redis 缓存  │  →  TTL=300s，下次查询直接命中
   └─────────────┘
```

### 4.2 Zone 资源同步流程

```
APScheduler 定时触发 / 用户手动触发
       │
       ▼
┌─────────────────────┐
│  POST /api/v1/zones │
│  /sync-all          │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  ZoneResourceService│  →  按 zone 逐个同步
│  .sync_all()        │
└──────────┬──────────┘
           │
    ┌──────┼──────┐
    ▼      ▼      ▼
┌──────┐ ┌────┐ ┌─────┐
│IDCRM │ │TCUM│ │CMDB │    ← 并行拉取
└──┬───┘ └──┬─┘ └──┬──┘
   │        │       │
   ▼        ▼       ▼
┌─────────────────────────┐
│  MySQL（本地持久化）     │
│  - zone_snapshots       │
│  - zone_positions       │
│  - zone_devices         │
│  - zone_stats           │
└─────────────────────────┘
```

### 4.3 工单流程

```
用户填写工单表单
       │
       ▼
┌─────────────────┐
│  Vue 前端       │  →  POST /api/v1/workorders
└─────────────────┘
       │
       ▼
┌─────────────────┐
│  WorkOrderService│
│  .create()      │
└────────┬────────┘
         │
    ┌────┼────┐
    ▼    ▼    ▼
┌──────┐ ┌───┐ ┌──────────┐
│MySQL │ │企微│ │腾讯文档   │
│持久化│ │通知│ │(OnePage) │    ← 推送到外部在线表格
└──────┘ └───┘ └──────────┘
```

### 4.4 企业微信机器人流程

```
企业微信用户发消息
       │
       ▼
┌─────────────────┐
│  Webhook 回调   │  ← 加密消息体
│  /api/v1/wecom  │
│  /callback      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  WecomBotWS     │  ← WebSocket 长连接（主动收发）
│  意图识别       │
└────────┬────────┘
         │
    ┌────┼────┬──────┐
    ▼    ▼    ▼      ▼
┌──┐ ┌──┐ ┌──┐ ┌──────┐
│查│ │查│ │查│ │AI对话 │
│主│ │联│ │知│ │      │
│机│ │系│ │识│ │      │
│  │ │人│ │库│ │      │
└──┘ └──┘ └──┘ └──────┘
```

---

## 五、数据库表结构

| 表名 | 用途 | 数据来源 |
|------|------|---------|
| `users` | 用户认证 | 本机录入 |
| `contacts` | 接口人通讯录 | 本机录入 |
| `knowledge_articles` | 知识库文章 | 本机录入 / 文件上传 |
| `knowledge_links` | 知识库链接 | 本机录入 |
| `knowledge_faqs` | FAQ 问答 | 本机录入 |
| `work_orders` | 工单记录 | 本机录入 + 腾讯文档同步 |
| `operation_logs` | 操作审计日志 | agent-guard 自动记录 |
| `zone_snapshots` | Zone 资源快照 | IDCRM + TCUM + CMDB 同步 |
| `zone_positions` | 虚拟化机位明细 | IDCRM 同步 |
| `zone_devices` | 设备清单 | TCUM 同步 |
| `yunxiao_host_machines` | 母机数据 | YunXiao 同步 |
| `yunxiao_inventory` | 可售卖库存 | YunXiao 同步 |
| `demand_requests` | 需求提单 | 本机录入 |
| `alembic_version` | DB 迁移版本 | alembic 管理 |

---

## 六、Client 模式对比

| 模式 | 原理 | 优点 | 缺点 |
|------|------|------|------|
| **mock** | 本地固定假数据 | 无网络依赖，开发调试快 | 数据不真实 |
| **browser** | Playwright 打开页面抓取 DOM | 绕过 API 鉴权，SSO 自动登录 | 慢（秒级），需要可视化浏览器 |
| **http** | Playwright 页面上下文 + `page.evaluate(fetch())` | 速度快 10x+，复用浏览器 cookie | 需要先有登录态 |
| **api** | 直连 OpenAPI | 最快最稳定 | 需要 AppID/Secret，目前占位未实现 |

---

## 七、关键文件映射

```
app/
├── main.py                 # 应用入口，中间件挂载，生命周期
├── config.py               # 环境变量配置（TEZ_* 前缀）
├── scheduler.py            # 定时任务调度器
├── routers/                # API 路由层（11个）
│   ├── hosts.py            # 主机查询 / zone 资源 / 同步
│   ├── contacts.py         # 接口人通讯录
│   ├── knowledge.py        # 知识库
│   ├── workorders.py       # 工单流
│   ├── op_logs.py          # 操作日志
│   ├── auth.py             # 用户认证
│   ├── cost.py             # 成本查询
│   ├── ai.py               # AI 助手
│   ├── yunxiao.py          # 云霄母机查询
│   └── wecom.py            # 企微回调
├── services/               # 业务逻辑层
│   ├── host_service.py     # 主机查询编排（聚合 CMDB+TCUM+IDCRM）
│   ├── zone_resource_service.py  # Zone 资源同步
│   ├── workorder_service.py      # 工单 CRUD + 腾讯文档推送
│   ├── contact_service.py        # 接口人路由
│   └── cache_service.py          # Redis 缓存（in-memory 降级）
├── clients/                # 外部平台对接层（每个平台三态实现）
│   ├── cmdb.py / cmdb_browser.py / cmdb_mock.py
│   ├── tcum.py / tcum_browser.py / tcum_http.py / tcum_mock.py
│   ├── idcrm.py / idcrm_browser.py / idcrm_http.py / idcrm_mock.py
│   ├── yunxiao.py / yunxiao_api.py / yunxiao_browser.py / yunxiao_mock.py
│   └── browser_session.py  # Playwright 浏览器会话管理
├── models/                 # SQLAlchemy ORM 模型
├── schemas/                # Pydantic 请求/响应模型
├── core/                   # 基础设施
│   └── guard/              # Agent-Guard 框架
│       ├── actor.py        # Actor 抽象（AI/Human/System）
│       ├── chain.py        # Guard 链装饰器
│       ├── middleware.py   # 全局请求拦截
│       ├── audit.py        # 审计日志 Guard
│       ├── exceptions.py   # Guard 异常体系
│       └── guards/         # 内置 Guard 实现
└── skills/                 # Playwright 自动化技能
    ├── idcrm_position_skill.py   # IDCRM 机位查询
    └── tencent_doc_skill.py      # 腾讯文档操作
```

---

## 八、部署拓扑

```
┌──────────────────────────────────────┐
│           本机（工位机器）             │
│                                       │
│  docker-compose up                    │
│  ├── nginx:80 → FastAPI:8000         │
│  ├── FastAPI:8000                     │
│  ├── MySQL:3306 (持久化)              │
│  ├── Redis:6379 (缓存)               │
│  ├── Playwright (Chromium 进程内)     │
│  └── APScheduler (进程内)             │
│                                       │
│  外部访问（只读）：                    │
│  ├── CMDB (cmdb.woa.com)             │
│  ├── TCUM (tcum.woa.com)             │
│  ├── IDCRM (idcrm.woa.com)           │
│  ├── YunXiao (yunxiao.vstation.woa.com)│
│  ├── 腾讯文档 (doc.weixin.qq.com)     │
│  └── 企业微信 (qyapi.weixin.qq.com)   │
└──────────────────────────────────────┘
```

---

## 九、当前模式配置建议

```bash
# .env 文件（推荐配置）
TEZ_CMDB_MODE=browser     # CMDB：通过浏览器抓取
TEZ_TCUM_MODE=browser     # TCUM：浏览器抓取（已稳定）
TEZ_IDCRM_MODE=http       # IDCRM：HTTP 直连（需先有浏览器登录态）
TEZ_YUNXIAO_MODE=api      # YunXiao：API 模式（headless 稳定）
```

当前运行状态（根据启动日志）：
- CMDB: `browser` — 登录态 OK
- TCUM: `browser` — 登录态 OK
- IDCRM: `http` — 需要浏览器先登录 SSO
- YunXiao: `mock` — 占位模式
