"""
write_file 工具：在 workspace 中创建或覆盖文件。

自动创建父目录。路径安全性由 validate_path 保证。
"""

from pathlib import Path

from tools.base import Tool
from tools.security import validate_path


class WriteFileTool(Tool):
    name = "write_file"
    description = (
        "Write content to a file in the workspace. "
        "Creates the file if it doesn't exist, or overwrites it if it does. "
        "Parent directories are created automatically."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative path from workspace root for the file to write.",
            },
            "content": {
                "type": "string",
                "description": "The full content to write to the file.",
            },
        },
        "required": ["path", "content"],
    }

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root

    def execute(self, path: str, content: str) -> str:
        target = validate_path(self.workspace_root, path)

        # 自动创建父目录
        target.parent.mkdir(parents=True, exist_ok=True)

        target.write_text(content, encoding="utf-8")

        return f"Successfully wrote {len(content)} characters to '{path}'."
