"""
move_file 工具：在 workspace 内移动文件。

自动创建目标路径的父目录。源路径和目标路径都经过边界校验。
"""

import shutil
from pathlib import Path

from tools.base import Tool
from tools.security import validate_path


class MoveFileTool(Tool):
    name = "move_file"
    description = (
        "Move a file from one location to another within the workspace. "
        "Parent directories of the destination are created automatically. "
        "Both source and destination must be within the workspace boundary."
    )
    parameters = {
        "type": "object",
        "properties": {
            "source": {
                "type": "string",
                "description": "Relative path from workspace root to the file to move.",
            },
            "destination": {
                "type": "string",
                "description": "Relative path from workspace root for the destination.",
            },
        },
        "required": ["source", "destination"],
    }

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root

    def execute(self, source: str, destination: str) -> str:
        src = validate_path(self.workspace_root, source)
        dst = validate_path(self.workspace_root, destination)

        if not src.exists():
            return f"Error: Source file '{source}' does not exist."
        if not src.is_file():
            return f"Error: Source path '{source}' is not a file."

        # 自动创建目标父目录
        dst.parent.mkdir(parents=True, exist_ok=True)

        shutil.move(str(src), str(dst))

        return f"Successfully moved '{source}' to '{destination}'."
