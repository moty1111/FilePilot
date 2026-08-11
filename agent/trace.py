"""
Trace 记录模块。

每一步 Agent 行为（LLM 思考、工具调用、工具结果）都会以一行 JSON
写入 trace.jsonl，用于可观测性和 Demo 展示。

格式示例:
    {"step": 1, "type": "tool_call", "tool": "search_files", \
"args": {"keyword": "Project Falcon"}, "result_summary": "Found 5 matches"}
    {"step": 2, "type": "tool_call", "tool": "read_file", \
"args": {"path": "notes/meeting.md"}, "result_summary": "Read 1200 chars"}

trace.jsonl 会被 security.HIDDEN_FILES 过滤，Agent 自身看不到它的存在。
"""

import json
from pathlib import Path
from typing import Any


class TraceRecorder:
    """将 Agent 执行过程以 JSONL 格式追加写入 trace 文件。"""

    def __init__(self, trace_path: Path) -> None:
        """
        Args:
            trace_path: trace.jsonl 的完整路径。
        """
        self.trace_path = trace_path
        self._step = 0

        # 确保父目录存在
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        # 每次启动 Agent 时清空旧 trace
        trace_path.write_text("", encoding="utf-8")

    def next_step(self) -> int:
        """步数 +1 并返回当前步号。"""
        self._step += 1
        return self._step

    @property
    def step(self) -> int:
        """当前步号。"""
        return self._step

    def record(
        self,
        step: int,
        record_type: str,
        tool: str | None = None,
        args: dict[str, Any] | None = None,
        result_summary: str | None = None,
        **extra: Any,
    ) -> None:
        """
        写入一条 trace 记录。

        Args:
            step: 步骤编号。
            record_type: 记录类型，如 "tool_call"、"llm_response"、"final"。
            tool: 工具名称（tool_call 类型时填写）。
            args: 工具参数（tool_call 类型时填写）。
            result_summary: 结果摘要。
            **extra: 其他需要记录的字段。
        """
        entry: dict[str, Any] = {
            "step": step,
            "type": record_type,
        }
        if tool is not None:
            entry["tool"] = tool
        if args is not None:
            entry["args"] = args
        if result_summary is not None:
            entry["result_summary"] = result_summary
        entry.update(extra)

        line = json.dumps(entry, ensure_ascii=False)
        with open(self.trace_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def summarize(self, text: str, max_len: int = 200) -> str:
        """
        将长文本截断为摘要，用于 trace 记录。

        Args:
            text: 原始文本。
            max_len: 摘要最大长度。

        Returns:
            截断后的摘要字符串。
        """
        text = text.replace("\n", " ").strip()
        if len(text) <= max_len:
            return text
        return text[:max_len] + "..."
