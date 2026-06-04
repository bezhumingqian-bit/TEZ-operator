"""AI 助手服务：调用大模型 API（兼容 OpenAI Chat 格式）。

支持：腾讯混元、DeepSeek、OpenAI GPT、CodeBuddy 等任何兼容接口。
配置在 .env 中：TEZ_AI_API_BASE / TEZ_AI_API_KEY / TEZ_AI_MODEL

优化策略：
- 缓存：相同问题 1 小时内直接返回缓存结果
- 上下文压缩：只取文档前 N 字符，避免发送过长内容
- 本地优先：常见问题用关键词匹配本地回答，不调 AI
"""

from __future__ import annotations

import hashlib
import time
from typing import Any

import httpx

from app.config import get_settings
from app.utils.logger import get_logger

log = get_logger(__name__)

# ─── 回复缓存（内存，1小时过期）───
_response_cache: dict[str, tuple[float, dict]] = {}
CACHE_TTL = 3600  # 1 小时

# ─── 常见问题本地回答（不调 AI，零 token） ───
LOCAL_ANSWERS: dict[str, str] = {
    "tez是什么": "TEZ（Tencent Edge Zone）是腾讯云边缘可用区产品，在运营商机房部署计算/网络/存储资源，为客户提供低延迟（5-10ms）的云服务。目前国内有 30+ 节点，支持 CVM、裸金属、CLB 等产品。",
    "怎么提工单": "在左侧菜单「工单流转」页面，点击「新建工单」按钮，选择工单类型（投放/搬迁），填写标题、固资号、目标可用区等信息后提交即可。",
    "搬迁流程": "搬迁标准流程：1. 确认目标机位（数全通查空闲位）→ 2. 确认 sideband=否 → 3. 确认 TPC → 4. 清 .backup → 5. 提搬迁工单 → 6. 等待执行 → 7. 验证上线状态",
    "母机故障怎么处理": "母机故障处理：1. 确认故障现象（掉线/性能异常）→ 2. 联系现场确认硬件状态 → 3. 提故障工单 → 4. 等待更换/修复 → 5. 重新投放验证",
    "成本怎么算": "TEZ 成本 = 物理机折旧 + 机位电费(400-650元/月) + 运营成本(6%)。过保机型物理机成本为0，只剩机位+运营成本，性价比最高。",
}

# 系统提示词
SYSTEM_PROMPT = """你是 TEZ 边缘可用区运营平台的 AI 助手。你的知识涵盖：
- TEZ 产品架构（边缘可用区、节点、机型、机位）
- 竞争对手分析（AWS Local Zone、阿里云 ENS、Cloudflare、华为云 IEC）
- 运维操作流程（投放、搬迁、母机故障、工单流转）
- 机型成本与定价

请用简洁专业的中文回答，必要时使用表格或列表。如果问题超出你的知识范围，请明确说明。"""


def _cache_key(message: str, context_type: str | None) -> str:
    """生成缓存 key。"""
    raw = f"{message.strip().lower()}|{context_type or ''}"
    return hashlib.md5(raw.encode()).hexdigest()


def _get_cached(key: str) -> dict | None:
    """获取缓存的回复（未过期）。"""
    if key in _response_cache:
        ts, data = _response_cache[key]
        if time.time() - ts < CACHE_TTL:
            return data
        del _response_cache[key]
    return None


def _set_cache(key: str, data: dict) -> None:
    """写入缓存。"""
    # 限制缓存大小（最多 200 条）
    if len(_response_cache) > 200:
        # 淘汰最旧的一半
        sorted_keys = sorted(_response_cache, key=lambda k: _response_cache[k][0])
        for k in sorted_keys[:100]:
            del _response_cache[k]
    _response_cache[key] = (time.time(), data)


def _try_local_answer(message: str) -> str | None:
    """尝试用本地关键词匹配回答常见问题（不消耗 token）。"""
    msg_lower = message.lower().strip()
    for keywords, answer in LOCAL_ANSWERS.items():
        if keywords in msg_lower or msg_lower in keywords:
            return answer
    return None


class AIService:
    """AI 助手服务。"""

    # 上下文长度限制（字符数）
    MAX_CONTEXT_PER_DOC = 1500  # 每篇文档最多取 1500 字
    MAX_TOTAL_CONTEXT = 6000   # 总上下文最多 6000 字
    MAX_HISTORY_TURNS = 4      # 对话历史最多保留 4 轮（8条消息）

    def __init__(self):
        self._settings = get_settings()

    @property
    def is_configured(self) -> bool:
        """检查 AI 是否已配置。"""
        return bool(self._settings.ai_api_base and self._settings.ai_api_key)

    async def chat(
        self,
        user_message: str,
        context: str | None = None,
        context_type: str | None = None,
        history: list[dict] | None = None,
    ) -> dict[str, Any]:
        """调用 AI 模型生成回复。

        优化：
        1. 先尝试本地回答（0 token）
        2. 再查缓存（0 token）
        3. 最后才调 API

        Returns:
            {"reply": str, "model": str, "usage": dict, "source": "local"|"cache"|"api"}
        """
        # 1. 本地回答（常见问题）
        local = _try_local_answer(user_message)
        if local and not history:  # 有历史说明是多轮对话，不用本地
            log.info("ai.local_answer", question=user_message[:30])
            return {"reply": local, "model": "local", "usage": {}, "source": "local"}

        # 2. 缓存命中
        cache_key = _cache_key(user_message, context_type)
        cached = _get_cached(cache_key)
        if cached and not history:  # 多轮对话不用缓存
            log.info("ai.cache_hit", question=user_message[:30])
            cached["source"] = "cache"
            return cached

        # 3. 调用 API
        if not self.is_configured:
            return {"reply": "AI 助手未配置，请在 .env 中设置 TEZ_AI_API_BASE 和 TEZ_AI_API_KEY", "model": "", "usage": {}, "source": "error"}

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # 添加上下文（压缩到限制内）
        if context:
            truncated = context[:self.MAX_TOTAL_CONTEXT]
            messages.append({"role": "system", "content": f"参考资料：\n{truncated}"})

        # 添加历史（限制轮数）
        if history:
            messages.extend(history[-(self.MAX_HISTORY_TURNS * 2):])

        messages.append({"role": "user", "content": user_message})

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{self._settings.ai_api_base.rstrip('/')}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._settings.ai_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self._settings.ai_model,
                        "messages": messages,
                        "max_tokens": self._settings.ai_max_tokens,
                        "temperature": 0.7,
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            reply = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            model = data.get("model", self._settings.ai_model)

            result = {"reply": reply, "model": model, "usage": usage, "source": "api"}

            # 写入缓存
            _set_cache(cache_key, result.copy())

            log.info("ai.api_call", model=model, tokens=usage.get("total_tokens"), msg_len=len(user_message))
            return result

        except httpx.HTTPStatusError as e:
            log.error("ai.http_error", status=e.response.status_code, body=e.response.text[:200])
            return {"reply": f"AI 接口返回错误 ({e.response.status_code})，请检查配置", "model": "", "usage": {}, "source": "error"}
        except Exception as e:
            log.error("ai.error", error=str(e))
            return {"reply": f"AI 调用失败: {str(e)[:100]}", "model": "", "usage": {}, "source": "error"}

    async def analyze_competitive(self, documents_content: str, question: str = "") -> dict[str, Any]:
        """竞争分析专用：基于文档内容回答问题或生成分析。"""
        prompt = question or "请基于以上竞分资料，生成一份结构化的竞争分析摘要，包含各厂商优劣势对比和建议。"
        return await self.chat(prompt, context=documents_content, context_type="competitive")

    async def answer_ops_question(self, question: str, knowledge_context: str = "") -> dict[str, Any]:
        """运维问答：基于知识库内容回答运维问题。"""
        return await self.chat(question, context=knowledge_context, context_type="knowledge")
