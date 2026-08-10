"""
LLM 客户端封装模块。

基于 OpenAI SDK 封装，兼容 OpenAI 官方 API 及第三方兼容端点
（如 DeepSeek、通义千问等）。

核心功能：
- chat()：发送对话请求（支持 function calling / tool use）
- 内置 token 用量统计（prompt / completion / 总调用次数）
- reset_usage()：重置统计（每次新任务前调用）
"""

from typing import Any

from openai import OpenAI

from core.config import settings


class LLMClient:
    """
    LLM 客户端，封装 OpenAI SDK 调用逻辑。

    用法:
        client = LLMClient()
        result = client.chat(messages=[...], tools=[...])
        # result = {"content": "...", "tool_calls": [...], "usage": {...}}
    """

    def __init__(self) -> None:
        """初始化 OpenAI 客户端和 token 统计计数器。"""
        self.client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
        self.model = settings.model_name

        # token 用量统计
        self._total_prompt_tokens: int = 0
        self._total_completion_tokens: int = 0
        self._total_calls: int = 0

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str = "auto",
    ) -> dict[str, Any]:
        """
        发送对话请求，返回模型响应。

        Args:
            messages: 对话消息列表，格式同 OpenAI Chat Completions API。
                      例如: [{"role": "system", "content": "..."}, ...]
            tools: 可用的工具定义列表（function calling）。
                   为 None 时不传 tools 参数。
            tool_choice: 工具选择策略，默认 "auto"。
                        可选值: "auto" | "none" | "required" | {"type": "function", ...}

        Returns:
            dict 包含:
            - content: 模型文本回复（可能为空，当模型选择只调用工具时）
            - tool_calls: 工具调用列表，无调用时为 None
            - usage: 本次调用的 token 统计
        """
        # 构建 API 请求参数
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice

        # 调用 API
        response = self.client.chat.completions.create(**kwargs)

        # 提取响应内容
        choice = response.choices[0]
        message = choice.message

        result: dict[str, Any] = {
            "content": message.content,
            "tool_calls": None,
            "usage": {},
        }

        # 提取 tool_calls（如果模型决定调用工具）
        if message.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        # arguments 是 JSON 字符串，由调用方解析
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
            ]

        # 记录 token 用量
        if response.usage:
            result["usage"] = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
            self._total_prompt_tokens += response.usage.prompt_tokens
            self._total_completion_tokens += response.usage.completion_tokens

        self._total_calls += 1
        return result

    def get_total_usage(self) -> dict[str, int]:
        """
        获取累计 token 用量统计。

        Returns:
            dict 包含:
            - prompt_tokens: 累计输入 token 数
            - completion_tokens: 累计输出 token 数
            - total_tokens: 累计总 token 数
            - total_calls: 累计 API 调用次数
        """
        return {
            "prompt_tokens": self._total_prompt_tokens,
            "completion_tokens": self._total_completion_tokens,
            "total_tokens": self._total_prompt_tokens + self._total_completion_tokens,
            "total_calls": self._total_calls,
        }

    def reset_usage(self) -> None:
        """重置 token 统计。每次新任务开始前调用。"""
        self._total_prompt_tokens = 0
        self._total_completion_tokens = 0
        self._total_calls = 0
