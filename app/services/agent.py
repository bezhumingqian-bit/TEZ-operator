"""AI Agent 循环服务:OpenAI Function Calling 多轮工具调用。

输入:用户消息 + 可选历史
输出:最终回复 + 工具调用轨迹

循环逻辑:
1. 把 tools 列表发给 LLM
2. 若 LLM 返回 tool_calls → 顺序执行工具,结果回灌,回到 1
3. 若 LLM 返回普通 content → 结束循环
4. 最多 5 轮迭代(防死循环)
"""
from __future__ import annotations

import json
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.services.agent_tools import TOOL_EXECUTORS, TOOL_SCHEMAS
from app.utils.logger import get_logger

log = get_logger(__name__)

MAX_ITERATIONS = 5
MAX_TOOL_RESULT_CHARS = 4000  # 单个工具结果最多 4000 字符(防超长)
LLM_TIMEOUT_S = 60
HISTORY_MAX_TURNS = 4  # 最多保留 4 轮历史(8 条消息)


SYSTEM_PROMPT = """你是 TEZ 边缘可用区运营平台的 AI 运营助手。
你可以使用工具查询真实数据来回答问题。

可用工具及场景：
- query_host：查某台机器的位置、状态、负责人
- search_knowledge：搜运维手册、SOP、故障处理流程（可看完整文章内容）
- list_zones：列出所有可用区
- get_zone_detail：查某可用区的机位总数、空闲位、在线/离线设备数
- query_inventory：查云霄新机型可售卖库存（按可用区/实例族/实例类型）
- check_online_capacity：判断某可用区能否上线新设备（空闲机位 + 库存概要）
- list_my_workorders：查工单列表（搬迁单、投放单等）

重要约束：
- query_host 只查本地数据库(7 天内有效)，不触发 CMDB/TCUM 浏览器
- 数据可能略陈旧，引用时说明"本地缓存"
- 不知道就说不知道，不要编造数据
- 多步骤问题可以调用多个工具综合回答
- 不要泄漏成本、定价等敏感数据

回答要求：
- 简洁专业，使用中文
- 引用具体数据而不是泛泛而谈
- 涉及数字时直接给出数值+单位
"""


class AgentService:
    """Agent 服务:工具调用循环。"""

    def __init__(self) -> None:
        self._settings = get_settings()

    @property
    def is_configured(self) -> bool:
        return bool(self._settings.ai_api_base and self._settings.ai_api_key)

    async def run(
        self,
        user_message: str,
        session: AsyncSession | None = None,
        history: list[dict] | None = None,
    ) -> dict[str, Any]:
        """执行 agent 循环。

        Returns:
            {
                "reply": str,
                "tool_calls": [{"name", "args", "ok", "result_preview"}],
                "iterations": int,
                "model": str,
                "usage": dict,
                "source": "agent",
            }
        """
        if not self.is_configured:
            return {
                "reply": "AI 未配置,请在 .env 设置 TEZ_AI_API_BASE 和 TEZ_AI_API_KEY",
                "tool_calls": [],
                "iterations": 0,
                "model": "",
                "usage": {},
                "source": "error",
            }

        messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        if history:
            # 限制历史轮数,避免 context 爆炸
            messages.extend(history[-(HISTORY_MAX_TURNS * 2) :])
        messages.append({"role": "user", "content": user_message})

        tool_calls_log: list[dict] = []
        total_usage: dict = {}
        iterations = 0
        final_reply = ""
        model_name = self._settings.ai_model

        for iteration in range(MAX_ITERATIONS):
            iterations += 1
            log.info("agent.iteration", iter=iteration, msg_count=len(messages))

            try:
                resp_data = await self._call_llm(messages, tools=TOOL_SCHEMAS)
            except httpx.HTTPStatusError as exc:
                log.error("agent.llm_http_error", status=exc.response.status_code, body=exc.response.text[:200])
                return {
                    "reply": f"AI 接口返回错误({exc.response.status_code}),请检查配置",
                    "tool_calls": tool_calls_log,
                    "iterations": iterations,
                    "model": model_name,
                    "usage": total_usage,
                    "source": "error",
                }
            except Exception as exc:  # noqa: BLE001
                log.error("agent.llm_error", error=str(exc))
                return {
                    "reply": f"AI 调用失败: {str(exc)[:200]}",
                    "tool_calls": tool_calls_log,
                    "iterations": iterations,
                    "model": model_name,
                    "usage": total_usage,
                    "source": "error",
                }

            # 累计 usage
            if "usage" in resp_data:
                u = resp_data["usage"]
                for k, v in u.items():
                    if isinstance(v, (int, float)):
                        total_usage[k] = total_usage.get(k, 0) + v

            choice = resp_data.get("choices", [{}])[0]
            msg = choice.get("message", {})
            model_name = resp_data.get("model", model_name)

            # 1. 模型直接返回 content(无 tool_call) → 结束
            if msg.get("content") and not msg.get("tool_calls"):
                final_reply = msg["content"]
                messages.append(msg)
                log.info("agent.final_reply_direct", iter=iteration, reply_len=len(final_reply))
                break

            # 2. 模型请求 tool_calls
            tool_calls = msg.get("tool_calls") or []
            if not tool_calls:
                final_reply = msg.get("content") or "（AI 返回为空）"
                if msg:
                    messages.append(msg)
                break

            # 把 assistant 消息(含 tool_calls)push 进历史
            messages.append(msg)

            # 3. 顺序执行所有 tool_calls
            for tc in tool_calls:
                fn_name = (tc.get("function") or {}).get("name", "")
                fn_args_raw = (tc.get("function") or {}).get("arguments", "")
                tc_id = tc.get("id", "")

                # 解析 args
                try:
                    fn_args = json.loads(fn_args_raw) if fn_args_raw else {}
                except json.JSONDecodeError:
                    fn_args = {}

                # 执行
                log.info("agent.tool_call", name=fn_name, args=fn_args)
                executor = TOOL_EXECUTORS.get(fn_name)
                if executor is None:
                    result: dict = {"ok": False, "error": f"未知工具: {fn_name}"}
                else:
                    try:
                        result = await executor(fn_args, session)
                    except Exception as exc:  # noqa: BLE001
                        log.error("agent.tool_exec_error", name=fn_name, error=str(exc))
                        result = {"ok": False, "error": f"工具执行失败: {str(exc)[:200]}"}

                # 截断超长结果
                result_str = json.dumps(result, ensure_ascii=False, default=str)
                truncated = len(result_str) > MAX_TOOL_RESULT_CHARS
                if truncated:
                    result_str = result_str[:MAX_TOOL_RESULT_CHARS] + "...(已截断)"

                # 记录日志(给前端展示)
                tool_calls_log.append({
                    "name": fn_name,
                    "args": fn_args,
                    "ok": bool(result.get("ok")),
                    "result_preview": result_str[:300],
                    "truncated": truncated,
                })

                # 把工具结果 push 给 LLM
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": result_str,
                })
        else:
            # 达到 max iterations 仍未收敛
            log.warning("agent.max_iterations_reached", iterations=MAX_ITERATIONS)
            if not final_reply:
                final_reply = "（AI 达到最大工具调用轮次,未生成最终回复,请简化问题重试）"

        log.info("agent.done", iterations=iterations, tool_calls=len(tool_calls_log),
                 reply_len=len(final_reply))
        return {
            "reply": final_reply,
            "tool_calls": tool_calls_log,
            "iterations": iterations,
            "model": model_name,
            "usage": total_usage,
            "source": "agent",
        }

    async def _call_llm(self, messages: list[dict], tools: list[dict]) -> dict:
        """单次 LLM 调用,支持 tools 字段。"""
        payload: dict[str, Any] = {
            "model": self._settings.ai_model,
            "messages": messages,
            "max_tokens": self._settings.ai_max_tokens,
            "temperature": 0.5,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        async with httpx.AsyncClient(timeout=LLM_TIMEOUT_S) as client:
            resp = await client.post(
                f"{self._settings.ai_api_base.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._settings.ai_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()


class StreamingAgent:
    """流式 Agent：SSE 推送工具调用进度 + 逐字输出。"""

    def __init__(self, svc: AgentService, user_message: str,
                 session: AsyncSession | None = None, history: list[dict] | None = None) -> None:
        self._svc = svc
        self._user_message = user_message
        self._session = session
        self._history = history or []
        self._settings = svc._settings

    async def run(self):
        """主循环：返回 SSE 事件流。

        事件格式：
        - {"event": "tool_call", "data": {"name", "args"}}
        - {"event": "tool_result", "data": {"name", "ok", "source"}}
        - {"event": "text", "data": "文字内容..."}
        - {"event": "done", "data": {"usage", "tool_calls", "model"}}
        - {"event": "error", "data": {"message"}}
        """
        if not self._svc.is_configured:
            yield {"event": "error", "data": {"message": "AI 未配置"}}
            return

        messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        if self._history:
            messages.extend(self._history[-(HISTORY_MAX_TURNS * 2):])
        messages.append({"role": "user", "content": self._user_message})

        tool_calls_log: list[dict] = []
        total_usage: dict[str, int] = {}
        model_name = self._settings.ai_model

        for iteration in range(MAX_ITERATIONS):
            # Step 1: 非流式调用，快速判断是否需要工具
            try:
                resp = await self._svc._call_llm(messages, tools=TOOL_SCHEMAS)
            except Exception as exc:
                yield {"event": "error", "data": {"message": str(exc)[:200]}}
                return

            if "usage" in resp:
                for k, v in resp["usage"].items():
                    if isinstance(v, (int, float)):
                        total_usage[k] = total_usage.get(k, 0) + int(v)

            choice = resp["choices"][0]
            msg = choice["message"]
            model_name = resp.get("model", model_name)

            # 场景 A：直接回答 → 流式输出
            if msg.get("content") and not msg.get("tool_calls"):
                messages.append(msg)
                async for chunk in self._stream_text(messages):
                    yield chunk
                yield {
                    "event": "done",
                    "data": {"usage": total_usage, "tool_calls": tool_calls_log, "model": model_name},
                }
                return

            # 场景 B：工具调用
            tool_calls = msg.get("tool_calls") or []
            if not tool_calls:
                yield {"event": "error", "data": {"message": "AI 返回为空"}}
                return

            messages.append(msg)

            for tc in tool_calls:
                fn_name = (tc.get("function") or {}).get("name", "")
                fn_args_raw = (tc.get("function") or {}).get("arguments", "")
                tc_id = tc.get("id", "")

                try:
                    fn_args = json.loads(fn_args_raw) if fn_args_raw else {}
                except json.JSONDecodeError:
                    fn_args = {}

                # 通知前端：工具开始执行
                yield {"event": "tool_call", "data": {"name": fn_name, "args": fn_args}}

                executor = TOOL_EXECUTORS.get(fn_name)
                if executor is None:
                    tool_result: dict = {"ok": False, "error": f"未知工具: {fn_name}"}
                else:
                    try:
                        tool_result = await executor(fn_args, self._session)
                    except Exception as exc:
                        tool_result = {"ok": False, "error": f"工具执行失败: {str(exc)[:200]}"}

                # 提取来源
                source = ""
                if tool_result.get("ok"):
                    if fn_name == "query_host":
                        source = f"本地缓存({tool_result.get('last_sync_at', '')})"
                    elif fn_name == "get_zone_detail":
                        source = f"本地同步({tool_result.get('zone', {}).get('last_sync_at', '')})"
                    elif fn_name == "search_knowledge":
                        arts = tool_result.get("articles", [])
                        source = f"知识库({arts[0]['title'] if arts else '无匹配'})"
                    elif fn_name == "list_my_workorders":
                        source = f"工单表({tool_result.get('total', 0)}条)"

                yield {"event": "tool_result", "data": {"name": fn_name, "ok": bool(tool_result.get("ok")), "source": source}}

                tool_calls_log.append({
                    "name": fn_name,
                    "args": fn_args,
                    "ok": bool(tool_result.get("ok")),
                    "source": source,
                })

                result_str = json.dumps(tool_result, ensure_ascii=False, default=str)
                if len(result_str) > MAX_TOOL_RESULT_CHARS:
                    result_str = result_str[:MAX_TOOL_RESULT_CHARS] + "...(已截断)"

                messages.append({"role": "tool", "tool_call_id": tc_id, "content": result_str})

            # 工具全部执行完 → 流式输出最终回答
            async for chunk in self._stream_text(messages):
                yield chunk

            yield {
                "event": "done",
                "data": {"usage": total_usage, "tool_calls": tool_calls_log, "model": model_name},
            }
            return

        yield {"event": "error", "data": {"message": "达到最大工具调用轮次"}}

    async def _stream_text(self, messages: list[dict]):
        """流式调用 LLM，逐字 yield text 事件。"""
        payload: dict[str, Any] = {
            "model": self._settings.ai_model,
            "messages": messages,
            "max_tokens": self._settings.ai_max_tokens,
            "temperature": 0.5,
            "stream": True,
        }

        try:
            async with httpx.AsyncClient(timeout=LLM_TIMEOUT_S) as client:
                async with client.stream(
                    "POST",
                    f"{self._settings.ai_api_base.rstrip('/')}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._settings.ai_api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            text = delta.get("content", "")
                            if text:
                                yield {"event": "text", "data": text}
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
        except Exception as exc:
            log.warning("agent.stream_error", error=str(exc))
            yield {"event": "error", "data": {"message": str(exc)[:200]}}
