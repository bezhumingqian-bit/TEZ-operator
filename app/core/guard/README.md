# agent-guard（TEZ Operator 内部使用）

> 物理级 AI Agent 安全约束框架。M3 阶段正式启用，当前为 PoC 状态。

## 当前状态（M1 → M2 过渡期）

| 层级 | 状态 | 说明 |
|---|---|---|
| **L4 中间件** | ✅ 已上线 | `HarnessMiddleware` 挂载在 `app.main.create_app`，识别 AI Actor + 审计 |
| **L4 装饰器** | ✅ 就绪 | `@guard_chain` + 5 个内置 Guard（audit_log / soft_delete / version_check / idempotency / result_limit / query_timeout） |
| **L3 工具白名单** | ⏳ M3 W2 | 待规划 |
| **L2 CI 扫描** | ⏳ M3 W2 | 待规划 |
| **L1 提示词** | ⏳ M3 W3 | 待规划 |
| **L5 GuardedSession** | ⏳ M4 | 待规划 |

## 已在哪些地方生效

- `app/main.py`：全局挂载 `HarnessMiddleware`
- `app/services/host_service.py`：新增 `get_host_guarded()` 方法，演示 Guard 链用法
- `app/routers/*`：通过中间件自动识别 AI 调用并审计

## 怎么调用（业务侧）

### 方式 1：直接调 Guard 链（推荐，最强保护）

```python
from app.core.guard import Actor, ActorType, guard_chain, audit_log
from app.core.guard.guards import soft_delete, version_check, idempotency

actor = Actor(id="ai-agent", type=ActorType.AI)

@guard_chain(audit_log(), version_check(), soft_delete())
async def delete_host(asset_id: str, version: int, actor: Actor):
    return await db.delete(asset_id)
```

### 方式 2：让 AI 直接走 HTTP 接口（中间件自动审计）

```python
import httpx

# AI 客户端自动加 header 表明身份
resp = httpx.post(
    "http://tez-operator/api/v1/workorders",
    json={...},
    headers={
        "X-Actor-Id": "ai-agent-v1",
        "X-Actor-Type": "ai",
    },
)
# 中间件自动审计；op_type 推断为 write
# 默认套 audit_log + version_check
# 若 service 层主动用 @guard_chain，会自动被中间件捕获
```

## 测试覆盖

```bash
# 单元测试（17 个）
pytest tests/test_agent_guard.py

# 中间件单元测试（10 个）
pytest tests/test_harness_middleware.py

# 端到端测试（8 个，真实 app）
pytest tests/test_harness_e2e.py

# 全部
pytest tests/test_agent_guard.py tests/test_harness_middleware.py tests/test_harness_e2e.py
```

## 中间件行为速查

| 路径 | HTTP 方法 | op_type | 默认 Guard 链 |
|---|---|---|---|
| `/api/v1/workorders` | POST/PUT/PATCH | write | audit + version |
| `/api/v1/workorders/{id}/transition` | POST | **trigger** | audit + version + idempotency |
| `/api/v1/workorders/{id}` | DELETE | delete | audit + soft_delete |
| `/api/v1/yunxiao/sync` | POST | **trigger** | audit + version + idempotency |
| `/api/v1/knowledge/articles` | POST | write | audit + version |
| `/api/v1/auth/users` | POST/DELETE | write/delete | audit + version / soft_delete |
| `/api/v1/hosts/...` | GET | read | audit + result_limit(1000) |

> 完整规则见 `app/core/guard/middleware.py` 的 `PATH_OP_OVERRIDES`。

## M3 阶段计划

| 周 | 内容 |
|---|---|
| W1 | service 层关键写方法（workorder.create/transition/delete）套 @guard_chain |
| W2 | L3 工具白名单（AI 工具清单裁剪）+ L2 CI 扫描规则 |
| W3 | L1 system prompt 模板 + 第一个 AI Agent 接入 Harness |
| W4 | L5 GuardedSession（资源隔离层）PoC |

## 联系方式

- 设计文档：`.codebuddy/teams/tez-ops/docs/24-agent-guard设计规范.md`
- Issue: tez-ops team
