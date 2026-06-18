# TEZ Operator — Agent Guide

> 本文件面向 AI 编码助手。阅读本文件后，你应当能够在不询问用户的前提下，独立完成日常开发、Bug 修复和轻度重构任务。

---

## 1. 项目概述

**TEZ Operator** 是 TEZ 边缘可用区运营/运维内部工具平台。

- **核心功能**：边缘云资源查询（可用区、机型、带宽）、CMDB/IDCRM 浏览器自动化数据同步、知识库管理、竞品分析
- **后端**：Python 3.11+ · FastAPI · SQLAlchemy 2.x · Pydantic v2
- **前端**：Vue 3 · Element Plus · Vite · TypeScript · Pinia
- **部署**：Docker Compose（工位机），Uvicorn 运行在 8000 端口
- **版本**：统一为 `0.3.0a0`（前后端一致）

---

## 2. 目录结构约定

```
app/
├── main.py              # FastAPI 应用入口，注册 router / middleware / exception handler
├── config.py            # Pydantic-Settings，所有配置项的单一来源
├── models/              # SQLAlchemy ORM 模型（Declarative Base）
├── schemas/             # Pydantic v2 Schema（Request / Response / ORM）
├── routers/             # FastAPI APIRouter，按业务域拆分
├── services/            # 业务逻辑层，router 不准直接操作 model / client
├── clients/             # 外部系统浏览器自动化（Playwright）
│   └── base_browser.py  # 浏览器自动化基类 BaseBrowserImpl
├── utils/               # 纯工具函数，无业务逻辑，无外部依赖
│   ├── normalize.py     # 状态归一化（online/offline/maintenance 的单一来源）
│   └── device_classifier.py  # TEZ 设备分类的单一来源
└── skills/              # 业务技能 / 独立能力模块

web/
├── src/
│   ├── views/           # 页面级 Vue 组件
│   ├── components/      # 通用业务组件
│   ├── api/             # Axios 封装，按业务域拆分模块
│   ├── stores/          # Pinia Store
│   ├── utils/           # 前端工具函数
│   │   ├── formatters.ts
│   │   ├── role.ts
│   │   └── clipboard.ts
│   └── router/          # Vue Router 配置
├── vite.config.ts       # Vite 构建配置
└── package.json         # 版本号 = 0.3.0

tests/                   # pytest 测试目录
├── conftest.py          # 全局 fixtures（async client, db session, mock redis）
└── test_*.py            # 按业务域命名

alembic/                 # 数据库迁移脚本（Alembic）
scripts/                 # 运维脚本（数据导入、健康检查、重启等）
knowledge/               # 知识库文档源文件（.md / .xlsx / .docx）
data/                    # 运行时数据（截图、缓存、报告）
```

---

## 3. 编码规范

### 3.1 Python

- **Formatter / Linter**：`ruff`（line-length = 100，target = py311）
- **Import 排序**：ruff 自动处理，不要手动调整
- **类型注解**：公共函数必须标注参数和返回值类型；私有函数（`_` 开头）建议标注
- **异步**：I/O 操作（数据库、HTTP、Playwright）**必须**使用 `async/await`；纯计算可用同步

### 3.2 状态与分类 — 单一来源原则

**严禁**在业务代码里手写状态映射或设备分类逻辑。必须使用以下两个模块：

```python
from app.utils.normalize import _normalize_status
from app.utils.device_classifier import classify_device
```

- `_normalize_status(raw)`：将任意状态字符串归一化为 `online` / `offline` / `maintenance`
- `classify_device(module, status)`：返回 `is_tez`, `is_transitional`, `reason`, `status_category`

### 3.3 浏览器自动化 — 基类继承

所有浏览器客户端必须继承 `BaseBrowserImpl`：

```python
from app.clients.base_browser import BaseBrowserImpl

class SomeBrowserClient(BaseBrowserImpl):
    _log_prefix = "some_browser"
    # 复用 _fetch_rows, _try_finish_sso_flow, _safe_cell, _normalize_status
```

禁止在子类中重复实现 SSO 处理、单元格安全读取、状态归一化等逻辑。

### 3.4 前端

- **语言**：TypeScript，严格模式
- **组件**：Composition API + `<script setup>` 语法
- **样式**：Element Plus 变量优先，Scoped CSS 次之，不要写全局样式
- **格式化**：Prettier + ESLint（`npm run lint` / `npm run format`）
- **版本注入**：前端版本号通过 Vite 的 `define.__APP_VERSION__` 注入，禁止在代码中硬编码

### 3.5 API 设计

- 路由文件按业务域拆分（`auth.py`, `hosts.py`, `knowledge.py`, `analysis.py`…）
- 响应体统一封装，避免裸返回 ORM 对象
- 数据库操作必须在 `services/` 层完成，`routers/` 只负责校验和调度

---

## 4. 安全红线

违反以下任何一条，必须**立即修复**，不得以"暂时方案"为由保留：

| # | 规则 | 说明 |
|---|------|------|
| 1 | **JWT Secret Key 必须从环境变量读取** | `TEZ_JWT_SECRET_KEY` 必须配置在 `.env` 中；代码中只允许 fallback 默认值并打印 warning |
| 2 | **Password Salt 必须从环境变量读取** | `TEZ_PASSWORD_SALT` 同上 |
| 3 | **禁止 `v-html` 解析未过滤的 HTML** | Markdown 渲染必须使用 `html: false`；如需支持 HTML，必须做 DOMPurify 消毒 |
| 4 | **禁止在源码中硬编码敏感 URL / Token** | 腾讯文档 URL、API Key 等必须走环境变量 |
| 5 | **禁止 `eval()` / `exec()` 处理用户输入** | 即使"看起来安全"也不行 |
| 6 | **SQL 查询必须参数化** | 禁止字符串拼接 SQL；使用 SQLAlchemy ORM 或 `text()` 绑定参数 |
| 7 | **禁止范围蔓延（Scope Creep）** | 修一个 bug 时禁止顺手重构整个模块。执行修改前自问：这个改动是否在需求范围内？如果只是为了"好看"或"顺手"，立即停止 |

---

## 5. 测试

- **框架**：pytest + pytest-asyncio + pytest-cov + pytest-mock
- **运行**：`pytest`（默认跳过 `@pytest.mark.slow`）
- **覆盖率**：`pytest --cov=app`，omit `alembic/*`
- **Fixture 位置**：`tests/conftest.py`
- **Mock 外部依赖**：HTTP 请求用 `respx`，Redis 用 `fakeredis`，Playwright 用 `unittest.mock.AsyncMock`

> **已知问题**：如果本地未启动 Redis，`TestListZones` 相关测试会因缓存降级到内存缓存而返回真实数据导致断言失败。这不是 Bug，运行 `docker compose up -d redis` 即可解决。

### 5.1 对抗性验证（Verification Agent 思维）

> 来源：Claude Code 泄露源码 — Verification Agent 的设计原则是"证明代码有 bug"，而非"确认它能跑"。

AI 写完代码后，必须以**攻击者心态**做自检，不得默认"应该没问题"：

| # | 攻击维度 | 操作 |
|---|---------|------|
| 1 | **并发攻击** | 对 create-if-not-exists 路径想"两个同时请求会怎样" |
| 2 | **边界值** | 测试 `0`、`-1`、空字符串、超长字符串、Unicode、`MAX_INT` |
| 3 | **幂等性** | 同一请求发两次，会不会产生重复数据？ |
| 4 | **孤儿操作** | 尝试删除/引用不存在的 ID，会不会崩溃？ |
| 5 | **注入攻击** | 输入里带 SQL 关键词、HTML 标签、`../` 路径遍历 |

**防偷懒规则**：任何"PASS"结论必须附上实际执行的命令和输出。禁止仅通过读代码就判定通过。

---

## 6. 常用命令

```bash
# 后端 — 安装依赖
pip install -e ".[dev]"

# 后端 — 运行（开发）
uvicorn app.main:app --reload --port 8000

# 后端 — 测试
pytest
pytest --cov=app

# 后端 — 格式化 / Lint
ruff check --fix .
ruff format .

# 前端 — 安装依赖
cd web && npm install

# 前端 — 开发服务器
npm run dev          # http://localhost:5173

# 前端 — 构建
npm run build        # 产物在 web/dist/

# 前端 — 格式化 / Lint
npm run lint
npm run format

# 数据库迁移
alembic revision --autogenerate -m "describe"
alembic upgrade head

# Docker 部署
docker compose up -d
```

---

## 7. 部署与配置

### 7.1 环境变量（`.env`）

以下变量**必须在生产环境配置**，否则使用 fallback 默认值并打印 warning：

```bash
TEZ_JWT_SECRET_KEY=         # 必须：JWT 签名密钥
TEZ_PASSWORD_SALT=          # 必须：密码哈希盐值
TEZ_TENCENT_DOC_URL=        # 腾讯文档数据源 URL
TEZ_DATABASE_URL=           # MySQL 连接串
TEZ_REDIS_URL=              # Redis 连接串
```

### 7.2 Docker Compose

- 服务：`app` (FastAPI) + `nginx` + `mysql` + `redis`
- Uvicorn 运行在 8000 端口，Nginx 反向代理到 80 端口
- 前端静态文件由 Nginx 直接托管（`web/dist`）

---

## 8. 给 AI 的特别说明

### 8.1 修改范围最小化原则
- 修复 Bug 时，只改导致问题的最小代码路径，不要顺手重构无关代码
- 新增功能时，优先复用现有工具函数（`normalize.py`, `device_classifier.py`, `BaseBrowserImpl`）
- 不要在同一 PR / commit 中混合功能开发和代码重构

### 8.2 强制思维链（Chain-of-Thought）

**涉及 2 个及以上文件的修改，或任何跨层调用（如 router → 新增 service → 新增 client）时，必须按以下步骤执行：**

1. **🧭 分析**：列出所有需要修改的文件及原因；画出数据流（请求从哪进、经过哪几层、从哪出）
2. **🔍 依赖检查**：读取 `.kimi/code-context/call_chains.md` 和 `module_deps.md`，确认待改模块的现有依赖关系，避免破坏既有调用链
3. **📝 实施计划**：按文件逐个说明变更点；先写接口/Schema，再写实现，最后写测试
4. **🧪 验证**：每改完一个文件，运行相关测试；失败时必须分析根因，不得用"也许可以"猜测。**展示证据，不声称成功**——贴上测试输出、命令返回值或截图，而不是说"已完成"
5. **✅ 收尾**：确认无遗漏，给出改动总结

**简单任务（单文件、纯工具函数）可跳过步骤 2，但仍需在心里过一遍依赖影响。**

### 8.2b 强制反问检查（接收需求后、动手前，弹性分级）

**原则**：理解越模糊、影响范围越大，反问越彻底。简单明确的需求不问或少问。

#### 分级规则

| 等级 | 触发条件 | 反问要求 |
|------|---------|---------|
| 🟢 **轻** | 单文件、纯工具函数、需求完全明确（如"把 X 字段改成 Y 类型"） | 直接做，不强制问 |
| 🟡 **中** | 1-2 个仓库、涉及 service/router 联动、有命名/接口设计决策 | 至少列出 1 个「理解确认」+ 标注「不做」的范围 |
| 🔴 **重** | 3+ 仓库、跨服务调用、新增模块、需求含"支持/兼容/优化"但范围模糊 | **必须完整输出三问**（见下方），用户确认后再动手 |

#### 🔴 重度反问模板

收到需求后，AI 必须先输出：

```
【理解确认】我理解的改动范围是 <X>，对吗？

【反向约束】我假设不做以下事情，请确认：
- 不做的：<A/B/C>
- 旧逻辑不能动的：<D/E>

【模糊点待确认】
- <具体问题 1>
- <具体问题 2>
```

用户确认后，才开始分析 → 实施。

#### 自动触发反问的模糊信号

无论等级，只要需求中出现以下任一信号，**至少升一级处理**：
- 出现"支持/兼容/优化/重构"但没有说具体范围 → 升一级
- 改动跨多个服务或调用链不完整 → 至少 🟡
- 命名/协议/枚举来自外部系统，代码里查不到 → 至少 🟡
- 有多个现有接口看起来都能复用 → 至少 🟡
- 用户一句话需求（少于 20 字）→ 至少 🟡

**来源**：CVM-Bench 评测关键发现——需求不清晰时 AI 不提问直接猜，编码分通常 50 以下。

### 8.2c 防止过度工程化（YAGNI）

每完成一个改动，自查是否违反了以下任一规则。违反任一条 = 改多了：

| # | 规则 | 示例 |
|---|------|------|
| 1 | **不做未要求的功能** | 用户说"加个缓存"，不要顺带加监控/告警/统计 |
| 2 | **不重构无关代码** | 只改 `host_service.py`，不要顺手重命名 `normalize.py` 的变量 |
| 3 | **不为一次性操作建抽象** | 一个函数够用就不要建工厂类 |
| 4 | **不为你没改的代码加注释/docstring** | 不要"顺手完善文档" |
| 5 | **不防御不可能的场景** | 内部函数不要给每个参数加类型校验/非空保护 |

**来源**：Anthropic Claude Prompting Best Practices §五.9 + CVM-Bench 实践。

### 8.2d 上下文主动清理

AI 的上下文窗口是最稀缺资源。复杂任务完成后，**必须主动提醒用户清理上下文**：

- 包含 3+ 个仓库改动的任务执行完毕 → 提醒用新会话继续下一任务
- 同一问题被纠正 2 次以上 → 上下文已被失败方法污染，建议 `/clear` 后重来
- 长时间探索/调查任务结束后 → 提醒当前上下文已膨胀，后续任务质量可能下降

**来源**：Anthropic Claude Code Best Practices §七 + 社区实践（60k token 规则）。

### 8.3 不要修改的文件
- `alembic/versions/` 下的已有迁移脚本（除非明确是迁移本身的 Bug）
- `data/` 目录下的运行时数据文件
- `backup/` 目录下的脚本

### 8.4 代码上下文（Code Context）— 修改前必读

项目已配置自动代码图谱生成。修改代码前，**优先阅读以下文件**以快速理解依赖关系：

| 文件 | 内容 | 何时阅读 |
|------|------|---------|
| `.kimi/code-context/call_chains.md` | 关键调用链：router → service → client → model | 修改任何 API 或业务逻辑前 |
| `.kimi/code-context/module_deps.md` | 模块依赖关系全景 | 新增/删除模块、调整导入前 |
| `.kimi/code-context/class_index.md` | 所有类的属性与方法索引 | 修改类接口、新增方法前 |
| `.kimi/code-context/api_surface.md` | API 请求/响应 Schema 汇总 | 修改接口契约前 |
| `.kimi/shared_memory.md` | **公共记忆**：从代码库提炼的架构约束、设计模式、数据流契约、规范漂移风险点 | **每次进入项目时必读**，快速掌握全局上下文 |

**更新命令**：
```bash
python scripts/generate_code_context.py
```

> 如果代码上下文文件与源码不一致（比如新增了模块但未在上下文中体现），必须**先运行更新命令**，再基于最新上下文做修改。

#### 8.4.1 文档修剪原则

`AGENTS.md` 和 `.kimi/shared_memory.md` 必须保持精炼。**每条指令用后一问自查**："删掉这行会导致 AI 犯错吗？"不会 → 删除。

- 季度检查：逐一审查 AGENTS.md 和 shared_memory.md 的每一条，删除 AI 能从代码读到的信息（如"项目用 FastAPI"）、过时的架构说明、不再有效的风险点
- 目标：AGENTS.md < 400 行，shared_memory.md < 400 行
- 如果某项规则 AI 持续遵守得好，考虑降级为简写或删除（已经内化了）

**来源**：Anthropic Claude Code Best Practices §五.1——CLAUDE.md 无情修剪原则。

### 8.5 新增文件时
- Python 文件顶部保留标准编码声明 `# -*- coding: utf-8 -*-
- 路由文件必须在 `app/main.py` 中注册
- 前端 API 模块必须在对应 store / view 中引用
- **新增模块后，必须运行 `python scripts/generate_code_context.py` 更新代码上下文**

### 8.6 修改公共记忆（Shared Memory）
AI 完成以下类型的修改后，**必须检查 `.kimi/shared_memory.md` 是否需要同步更新**：

- 新增 / 删除 router、service、client、model 模块
- 修改关键数据流（如 HostService 的聚合逻辑、工单状态流转）
- 调整架构约束（如三态模式、继承关系、单一来源模块职责变化）
- 新增安全红线或全局工具函数
- 发现新的"规范漂移"风险点

**检查流程**：
1. 读取当前 `.kimi/shared_memory.md`
2. 对比本次修改是否影响其中的架构骨架、数据流、单一来源或风险点
3. 若需要更新，在任务收尾阶段主动提出，经用户确认后执行
4. 更新后同步修正本文件（AGENTS.md）中的相关引用（如有）

> 若仅修改纯实现细节（如 bug fix、样式调整、增加字段），通常无需更新公共记忆。

### 8.7 引入新依赖时
- Python：添加到 `pyproject.toml` 的 `[project.dependencies]` 或 `[project.optional-dependencies.dev]`
- Node.js：在 `web/` 目录下 `npm install -S <pkg>`
- 不要引入体积过大（>10MB）或维护状态差（1 年以上无更新）的依赖

### 8.8 知识库相关
- 知识库文章支持 `.md`、`.xlsx`、`.docx`、`.pdf` 格式
- `.docx` / `.pdf` 为二进制文件，读取时不能直接用 `read_text(encoding="utf-8")`，应回退到 `article.content`
- `category='manual'` 是内部手册，`category='competitive'` 是竞品分析

---

## 9. 故障排查速查

| 现象 | 可能原因 | 解决 |
|------|---------|------|
| `pytest` 2 个 zone 测试失败 | 本地 Redis 未启动，缓存降级到内存 | `docker compose up -d redis` |
| 前端构建后版本号不对 | `__APP_VERSION__` 未正确注入 | 检查 `web/vite.config.ts` 的 `define` |
| Playwright 浏览器启动失败 | Chromium 未安装 | `playwright install chromium` |
| 知识库 `.docx` 读取崩溃 | 用 `read_text()` 读二进制文件 | 已修复：检查 `knowledge.py` 的文件类型判断 |
| 登录后 token 无效 | `TEZ_JWT_SECRET_KEY` 使用了 fallback | 在 `.env` 中配置一致的秘密密钥 |

---

*Last updated: 2026-06-18 — 新增 §4.7 范围蔓延、§5.1 对抗性验证、§8.2b 反问检查、§8.2c 防止过度工程化、§8.2d 上下文清理、§8.4.1 文档修剪原则*
