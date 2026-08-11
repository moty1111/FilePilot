"""
Agent 核心循环模块。

AgentRunner 实现 Tool Calling 的自主 Agent Loop:
    1. 初始化 messages（system_prompt + user task）
    2. 调用 LLM，传入 tools schema
    3. LLM 返回 tool_calls -> 逐个执行工具 -> 结果回填到 messages
    4. 重复 2-3，直到 LLM 返回纯文本（无 tool_calls）或达到 max_steps

关键设计:
- Tool Calling: ToolRegistry.get_all_schemas() 传给 LLM
- Tool Result 回填: 以 role="tool" 消息追加到 messages
- 最大步数限制: 超过 max_steps 强制终止
- Prompt Injection 防护: System Prompt 明确文件内容是 untrusted data
- Trace 可观测: 每步记录到 trace.jsonl
"""

import json
from pathlib import Path
from typing import Any

from agent.system_prompt import get_system_prompt
from agent.trace import TraceRecorder
from core.config import settings
from core.llm_client import LLMClient
from tools import create_tool_registry


class AgentRunner:
    """
    Agent 执行器，实现完整的 Agent Loop。

    用法:
        runner = AgentRunner(workspace_path="./workspace")
        result = runner.run("找出所有提到 Project Falcon 的文件")
    """

    def __init__(
        self,
        workspace_path: Path | str | None = None,
        max_steps: int | None = None,
        trace_path: Path | str | None = None,
    ) -> None:
        """
        初始化 AgentRunner。

        Args:
            workspace_path: workspace 根目录，默认使用 settings.workspace_path。
            max_steps: 最大执行步数，默认使用 settings.max_steps。
            trace_path: trace.jsonl 路径，默认写到 workspace 目录下。
        """
        self.workspace_path = Path(workspace_path) if workspace_path else settings.workspace_path
        self.max_steps = max_steps if max_steps is not None else settings.max_steps

        # trace.jsonl 写在 workspace 根目录下
        if trace_path:
            self.trace_path = Path(trace_path)
        else:
            self.trace_path = self.workspace_path / "trace.jsonl"

        # 初始化组件
        self.llm_client = LLMClient()
        self.registry = create_tool_registry(
            workspace_root=self.workspace_path,
            max_file_chars=settings.max_file_chars,
            max_search_results=settings.max_search_results,
        )
        self.tracer = TraceRecorder(self.trace_path)

    def run(self, task: str) -> str:
        """
        执行用户任务，返回最终结果文本。

        Args:
            task: 用户的自然语言任务指令。

        Returns:
            Agent 最终回复文本。
        """
        # 重置 token 统计
        self.llm_client.reset_usage()

        # 初始化 messages
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": get_system_prompt(self.registry)},
            {"role": "user", "content": task},
        ]

        tools_schema = self.registry.get_all_schemas()

        print(f"--- Agent Loop Start ---")
        print(f"Task: {task}")
        print()

        # Agent Loop
        for step in range(1, self.max_steps + 1):
            print(f"[Step {step}/{self.max_steps}] Thinking...")

            # 调用 LLM
            response = self.llm_client.chat(
                messages=messages,
                tools=tools_schema,
            )

            content = response.get("content") or ""
            tool_calls = response.get("tool_calls")

            # 如果 LLM 没有调用工具，说明任务完成
            if not tool_calls:
                print(f"[Step {step}] No tool calls - task complete.")
                self.tracer.record(
                    step=step,
                    record_type="final",
                    result_summary=self.tracer.summarize(content),
                )
                print(f"\n--- Agent Loop End ---\n")
                self._print_usage()
                return content

            # LLM 返回了工具调用，需要先记录 assistant 消息（包含 tool_calls）
            assistant_message: dict[str, Any] = {
                "role": "assistant",
                "content": content if content else None,
                "tool_calls": tool_calls,
            }
            messages.append(assistant_message)

            # 逐个执行工具
            for tc in tool_calls:
                tool_name = tc["function"]["name"]
                raw_args = tc["function"]["arguments"]

                # 解析参数
                try:
                    tool_args = json.loads(raw_args) if raw_args else {}
                except json.JSONDecodeError:
                    tool_args = {}
                    error_msg = f"Error: Invalid JSON arguments: {raw_args}"
                    self._append_tool_result(messages, tc["id"], tool_name, error_msg)
                    self.tracer.record(
                        step=step,
                        record_type="tool_call",
                        tool=tool_name,
                        args={"_raw": raw_args},
                        result_summary=error_msg,
                    )
                    print(f"  -> {tool_name}({raw_args}) => [JSON parse error]")
                    continue

                print(f"  -> {tool_name}({tool_args})")

                # 执行工具
                result = self.registry.execute(tool_name, tool_args)

                # 记录 trace
                self.tracer.record(
                    step=step,
                    record_type="tool_call",
                    tool=tool_name,
                    args=tool_args,
                    result_summary=self.tracer.summarize(result),
                )

                # 回填工具结果到 messages
                self._append_tool_result(messages, tc["id"], tool_name, result)

                print(f"     => {self.tracer.summarize(result, 100)}")

        # 达到最大步数，强制终止
        print(f"\n[Max steps reached] Forcing termination at step {self.max_steps}.")
        self.tracer.record(
            step=self.max_steps,
            record_type="max_steps_reached",
            result_summary="Agent reached max_steps limit and was forced to stop.",
        )
        print(f"\n--- Agent Loop End (max steps) ---\n")
        self._print_usage()
        return "Agent reached the maximum number of steps and was forced to stop. " \
               "The task may not be fully completed."

    def _append_tool_result(
        self,
        messages: list[dict[str, Any]],
        tool_call_id: str,
        tool_name: str,
        result: str,
    ) -> None:
        """
        将工具执行结果以 role="tool" 消息追加到 messages 列表。

        Args:
            messages: 消息列表。
            tool_call_id: 对应的 tool_call ID。
            tool_name: 工具名称。
            result: 工具执行结果字符串。
        """
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": tool_name,
            "content": result,
        })

    def _print_usage(self) -> None:
        """打印 token 用量统计。"""
        usage = self.llm_client.get_total_usage()
        print(f"Token Usage:")
        print(f"  Prompt tokens:     {usage['prompt_tokens']}")
        print(f"  Completion tokens: {usage['completion_tokens']}")
        print(f"  Total tokens:      {usage['total_tokens']}")
        print(f"  API calls:         {usage['total_calls']}")
        print(f"  Trace file:        {self.trace_path}")
