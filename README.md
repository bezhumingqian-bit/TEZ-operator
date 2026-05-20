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
# {"status":"ok","db":"ok","redis":"ok"}
```

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

### 配置说明

所有配置走 `.env`，**不要硬编码任何凭据**。关键变量：

| 变量 | 说明 | 示例 |
|------|------|------|
| `APP_ENV` | 运行环境 | `dev` / `prod` |
| `MOCK_MODE` | 是否启用上游 mock | `true` / `false` |
| `DATABASE_URL` | MySQL 连接串 | `mysql+pymysql://...` |
| `REDIS_URL` | Redis 连接串 | `redis://localhost:6379/0` |
| `UPSTREAM_*_URL` | 上游平台地址 | `https://your-internal-platform.example.com` |

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
