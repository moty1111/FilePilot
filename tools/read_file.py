"""
read_file 工具：读取文件内容，支持分块读取和自动截断。

- 通过 offset / limit 参数支持大文件分块读取
- 单次返回不超过 max_file_chars 字符，超出时截断并提示 LLM 如何继续
"""

from pathlib import Path

from tools.base import Tool
from tools.security import validate_path


class ReadFileTool(Tool):
    name = "read_file"
    description = (
        "Read the content of a file in the workspace. "
        "Supports reading specific portions of large files using offset and limit. "
        "If a file is too large, the output will be truncated with a message "
        "telling you what offset to use for the next chunk."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative path from workspace root to the file.",
            },
            "offset": {
                "type": "integer",
                "description": "Line number to start reading from (0-based). Defaults to 0.",
                "default": 0,
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of lines to read. 0 means read until end or max chars.",
                "default": 0,
            },
        },
        "required": ["path"],
    }

    def __init__(self, workspace_root: Path, max_chars: int = 20000) -> None:
        self.workspace_root = workspace_root
        self.max_chars = max_chars

    def execute(self, path: str, offset: int = 0, limit: int = 0) -> str:
        target = validate_path(self.workspace_root, path)

        if not target.exists():
            return f"Error: File '{path}' does not exist."
        if not target.is_file():
            return f"Error: '{path}' is not a file."

        try:
            content = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = target.read_text(encoding="utf-8", errors="replace")

        lines = content.split("\n")
        total_lines = len(lines)

        # 确定读取范围
        start = max(0, offset)
        end = total_lines if limit <= 0 else min(start + limit, total_lines)
        chunk_lines = lines[start:end]
        chunk_text = "\n".join(chunk_lines)

        # 字符级截断
        char_truncated = False
        if len(chunk_text) > self.max_chars:
            chunk_text = chunk_text[: self.max_chars]
            char_truncated = True

        result = chunk_text

        # 如果还有更多内容，附加提示
        has_more = char_truncated or (end < total_lines)
        if has_more:
            actual_lines_shown = chunk_text.count("\n") + 1
            next_offset = start + actual_lines_shown
            result += (
                f"\n\n[... content truncated ...]\n"
                f"File has {total_lines} lines total. "
                f"Shown: lines {start + 1}-{start + actual_lines_shown}. "
                f"To read more, use offset={next_offset}."
            )

        return result
