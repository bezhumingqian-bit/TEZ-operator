# Operator

> 边缘云资源运维平台 — 把分散在多个内网平台里的运维动作，聚合到一个口子。

---

## 🎯 这是什么

本项目是一个**面向小团队（5–20 人）的内部运维聚合平台**。它把多源资产数据、工单流、知识沉淀、协作路由整合到统一的 Web 界面，让"找一台机器属于谁、谁该处理这个工单、相关文档在哪儿"这类问题在 30 秒内有答案。

### 不是什么

- ❌ **不是公开 SaaS**：仅供项目所属团队内部部署使用
- ❌ **不是底层资产管理平台**：不存机器源数据，只做**聚合层** —— 数据所有权仍在上游平台
- ❌ **不是 CI/CD 平台**：不替代发布流水线
- ❌ **不是监控告警系统**：不替代 Prometheus / 监控大盘

### 设计理念

> **"聚合而非替代"** ：把多个上游平台的数据、人、流程聚合在一起，做一层薄薄的运维工作台。

- 上游故障时不阻塞，自动降级到缓存数据
- 不持有真实业务数据的所有权，只做读视图 + 工单流编排
- 5–20 人量级，简单稳定第一，避免过度设计

---

## 🧩 五大核心模块

| 模块 | 一句话定位 | 状态 |
|------|----------|------|
| 🚦 **驾驶舱** | 团队当天事件 / 资源水位 / 待办一屏看完 | 规划中（M4） |
| 📋 **工单流** | 工单从录入、流转、关单到归档的全生命周期 | 规划中（M3） |
| 🔍 **资源查询** | 输入资产号 / IP / 区域，聚合多源信息返回机器全貌 | **建设中（M1）** |
| 👥 **接口人路由器** | 根据模块 / 区域 / 类型，自动路由到对应负责人 | 规划中（M2） |
| 📚 **知识中枢** | 沉淀运维 SOP、FAQ、对接信息，全文检索 | 规划中（M2） |

---

## ⚡ 30 秒快速启动（Mock 模式）

> 适合本地开发预览，不需要真实上游平台凭据。

```bash
# 1. 克隆仓库
git clone https://github.com/bezhumingqian-bit/TEZ-operator.git
cd TEZ-operator

# 2. 准备配置（默认 mock 模式）
cp .env.example .env

# 3. 起基础设施（MySQL + Redis）
./scripts/start.sh

# 4. 安装依赖 & 跑后端
uv sync
uv run uvicorn app.main:app --reload --port 8000

# 5. 打开 API 文档
open http://localhost:8000/docs
```

健康检查：

```bash
curl http://localhost:8000/health
# {"status":"ok","service":"tez-operator","version":"0.3.0-alpha"}
```

---

## 🌐 启用真实模式（Browser，W2）

> 当上游平台暂无 OpenAPI 凭据时，可启用 Playwright 浏览器自动化，复用工位机的 SSO 登录态查询真实数据。

```bash
# 1. 装 Playwright + Chromium
uv sync                     # 装 playwright python 包
uv run python -m playwright install chromium

# 2. 改 .env：把 TCUM 切到 browser 模式 + 填内网真实地址
#    TEZ_TCUM_MODE=browser
#    TEZ_TCUM_BASE_URL=<工位机能访问的 TCUM 内网地址>
#    TEZ_BROWSER_PROFILE_DIR=data/playwright-profile
#    TEZ_BROWSER_HEADLESS=false
#    TEZ_BROWSER_LOGIN_VALID_DAYS=7

# 3. 启动后端
uv run uvicorn app.main:app --reload --port 8000

# 4. 首次访问 /api/v1/hosts/search?q=TYSV00000001 时
#    会自动唤起 Chromium，扫码完成 SSO 登录后即可返回数据
#    登录态保存在 data/playwright-profile/，默认 7 天内复用免登
```

> IDCRM Browser 解析仍需 W4 真实页面样本，当前默认保持 `TEZ_IDCRM_MODE=mock`；样本到位前不要开启 `TEZ_IDCRM_MODE=browser`。
> `TEZ_BROWSER_IGNORE_HTTPS_ERRORS` 默认 `false`；仅内网自签证书导致浏览器无法访问时，才在本地 `.env` 显式改为 `true`。

**故障速查**：
- 首次唤起没出浏览器？检查 `chromium` 是否装了（`playwright install chromium`）。
- 多次访问后被踢回 SSO？（`BrowserAuthExpired`）— 后端会日志告警，可设 `TEZ_WECOM_WEBHOOK` 推到企微群；删 `data/playwright-profile/Default/Cookies` 后再次访问会再次扫码。
- 工位机重启后 profile 仍在？是的，登录态持久化跨进程。

> ⚠️ **数据安全**：`data/playwright-profile/` 已在 `.gitignore` 内，绝不入仓；任何抓取产物 / 截图 / cookie 同样不入仓（详见 `.codebuddy/teams/tez-ops/docs/16-数据安全规则.md`）。

---

## 🛠 技术栈

| 层 | 技术 |
|----|------|
| 后端 | FastAPI · SQLAlchemy 2.x · Pydantic v2 · APScheduler · Alembic |
| 数据 | MySQL 8 · Redis 7 |
| 前端 | Vue 3 · Element Plus · Vite |
| 上游适配 | httpx · [Playwright](https://playwright.dev/)（用于无 OpenAPI 的内网平台浏览器自动化） |
| 部署 | Docker Compose（工位机起步），后续迁 K8s |
| 工具链 | uv · ruff · pytest · structlog |

---

## 📁 项目结构

```
TEZ-operator/
├── app/                     # FastAPI 应用
│   ├── main.py              # 入口
│   ├── config.py            # Pydantic Settings
│   ├── deps.py              # 依赖注入
│   ├── routers/             # API 路由
│   ├── services/            # 业务编排
│   ├── clients/             # 上游平台适配器
│   ├── models/              # ORM 模型
│   ├── schemas/             # 请求/响应模型
│   └── utils/               # 通用工具
├── alembic/                 # 数据库迁移
├── tests/                   # pytest 单测 / 集成测试
├── scripts/                 # 一键启停 / 健康检查脚本
│   ├── start.sh
│   ├── stop.sh
│   ├── restart.sh
│   └── healthcheck.sh
├── nginx/                   # 前端反代配置
├── backup/                  # 备份脚本
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

> 真实数据、内部文档、上游平台凭据等敏感内容**不入仓**，统一保留在本地工作区。

---

## 👨‍💻 开发

### 环境要求

- Python `>= 3.11`
- Docker / Docker Compose
- [uv](https://github.com/astral-sh/uv)（推荐的 Python 包管理器）

### 常用命令

```bash
# 安装依赖（含 dev 依赖）
uv sync --all-extras

# 启动基础设施
./scripts/start.sh

# 跑测试
uv run pytest

# 跑测试 + 覆盖率
uv run pytest --cov=app --cov-report=term-missing

# 代码格式化
uv run ruff format .

# 静态检查
uv run ruff check . --fix

# 数据库迁移
uv run alembic upgrade head

# 新建迁移
uv run alembic revision --autogenerate -m "your message"
```

前端本地启动入口：
```bash
cd web && npm install && npm run dev
```

### 配置说明

所有配置走 `.env`，**不要硬编码任何凭据**。关键变量：

| 变量 | 说明 | 示例 |
|------|------|------|
| `TEZ_APP_ENV` | 运行环境 | `local` / `prod` |
| `TEZ_DATABASE_URL` | SQLAlchemy 连接串 | `mysql+pymysql://tez:tez@127.0.0.1:3306/tez_operator?charset=utf8mb4` |
| `TEZ_REDIS_URL` | Redis 连接串 | `redis://127.0.0.1:6379/0` |
| `TEZ_CCDB_MODE` / `TEZ_TCUM_MODE` / `TEZ_IDCRM_MODE` | 上游客户端模式 | `mock` / `api` / `browser` |
| `TEZ_CCDB_BASE_URL` / `TEZ_TCUM_BASE_URL` / `TEZ_IDCRM_BASE_URL` | 上游平台地址占位 | `http://tcum.example.com` |
| `TEZ_BROWSER_PROFILE_DIR` | Playwright 登录态目录 | `data/playwright-profile` |
| `TEZ_BROWSER_IGNORE_HTTPS_ERRORS` | 是否忽略 HTTPS 证书错误 | `false` |

完整变量见 [`.env.example`](.env.example)。

### Mock 数据示例

测试 / 开发使用以下虚构占位值，避免引入任何真实数据：

| 类型 | 占位 |
|------|------|
| 资产编号 | `TYSV00000001` |
| 内网 IP | `10.0.0.1` / `192.168.1.1` |
| 客户标识 | `customer_a` / `customer_b` |
| 节点 / 机房 | `idc_a` / `示例机房A1` |
| 用户名 | `alice` / `bob` |
| Zone | `zone_a` / `zone_b` / `zone_c` |

---

## 📊 测试与覆盖率

### 跑全部测试

```bash
# 基础（默认跳过 slow 性能基准）
uv run pytest

# 带覆盖率报告
uv run pytest --cov=app --cov-report=term-missing

# 含性能基准测试
uv run pytest -m slow
```

### 当前覆盖率（W3 v0.3.x-alpha）

整体覆盖率 **82%**（目标 ≥ 70%）。关键模块：

| 模块 | 覆盖率 |
|------|--------|
| `app/routers/hosts.py` | 100% |
| `app/services/host_service.py` | 97% |
| `app/services/cache_service.py` | 92% |
| `app/services/export_service.py` | 97% |
| `app/clients/ccdb_browser.py` | 95% |
| `app/clients/idcrm_browser.py` | 91% |
| `app/clients/tcum_browser.py` | 90% |
| `app/schemas/host.py` | 100% |
| `app/utils/parser.py` | 98% |

> ORM 模型（`app/models/`）与 alembic 迁移在覆盖率统计中 omit，由 `alembic upgrade head` 自身验证。

### 测试分类

- `tests/test_parser.py` — 输入识别（asset_id/ip/zone）
- `tests/test_clients.py` — 三家客户端 mock 路径
- `tests/test_tcum_browser.py` — TCUM Browser 解析（含 W3 status 中→英归一化）
- `tests/test_ccdb_browser.py` — CCDB Browser（W3 实现）
- `tests/test_idcrm_browser.py` — IDCRM Browser 框架占位（_parse_row 待 W4）
- `tests/test_browser_session.py` — Playwright 单例 + 登录态判定
- `tests/test_cache_service.py` — Redis 真路径 (fakeredis) + 内存降级
- `tests/test_host_service.py` — 三方融合 / 缓存 / partial 降级 / batch
- `tests/test_api_hosts.py` — Router 端到端（httpx ASGITransport）
- `tests/test_w3_features.py` — W3 专项：并发限流 / Excel 导出 / status Literal
- `tests/test_performance.py` — 性能基准（`-m slow`）

---

## 🚀 批量查询与并发限流

### `POST /api/v1/hosts/batch_search`

一次最多 100 条（`TEZ_BATCH_MAX_SIZE`），混合固资号 / IP。请求体：

```json
{ "queries": ["TYSV00000001", "10.0.0.5", "TYSV00000002"] }
```

### 限流策略

为避免一次性打开过多 Playwright tab（每条浏览器查询会占用一个 page），
后端用 `asyncio.Semaphore` 限制并发：

| 配置 | 默认值 | 含义 |
|------|--------|------|
| `TEZ_BATCH_CONCURRENCY` | 5 | 同时进行的查询数上限 |
| `TEZ_BATCH_MAX_SIZE` | 100 | 单次请求接受的最大条数 |

- 100 条以 5 并发跑，理论峰值 5 个 tab，工位机内存友好
- 单条失败（超时 / 4xx / 浏览器登录态失效）不影响其他条
- 失败信息在响应 `items[*].error` 字段返回

### `GET /api/v1/hosts/export?asset_ids=A,B,C`

导出 xlsx（中文表头，列序与 HostInfo 字段对齐），同样走并发限流。

---

## 🗺 里程碑路线图

| 里程碑 | 周期 | 内容 | 关键产出 |
|-------|------|------|---------|
| **M1** | 4 周 | 资源查询 MVP | 输入资产号 / IP / 区域，聚合多源数据返回机器全貌（只读） |
| **M2** | 4 周 | 知识中枢 + 接口人路由器 | SOP / FAQ 沉淀；按模块自动路由对应负责人 |
| **M3** | 6 周 | 工单流 + 运营总表同步 | 工单录入流转、与运营总入口表格双向同步 |
| **M4** | 4 周 | 驾驶舱 | 全团队事件 / 水位 / 待办一屏看完 |
| **M5+** | — | 迁 K8s / 高可用 | 工位机部署稳定运行后再迁 |

> 总体节奏：约 18 周，完成核心 4 个里程碑。

---

## 🤝 贡献指南

1. 提 issue 描述问题 / 需求，先对齐再写代码
2. 从 `main` 拉分支 `feat/xxx` / `fix/xxx`
3. 提交前确保：
   - `uv run ruff check .` 无报错
   - `uv run pytest` 全绿
   - **不提交任何真实数据 / 凭据**（详见 [`.env.example`](.env.example) 与 `.gitignore`）
4. 提 PR，描述变更点和测试方式

### 提交规范

```
<type>(<scope>): <subject>

例：
feat(resource): 资源查询接口聚合多源数据
fix(client): 上游超时时降级到缓存
docs(readme): 补充开发命令
```

`type` 可选：`feat` / `fix` / `docs` / `refactor` / `test` / `chore`

---

## 🔒 数据安全

- 所有真实数据（资产编号 / IP / 客户名 / 内网平台 URL / 凭据）**永不入仓**
- `.env` 已在 `.gitignore` 中排除
- 提交前请用 `git diff --cached` 自查
- 详见 `.gitignore` 中的排除规则

---

## 📄 License

MIT — 详见 [LICENSE](./LICENSE)

---

## 🙏 致谢

感谢所有上游平台、开源社区以及参与项目的同事。
