"""
list_files 工具：列出 workspace 中的文件和目录结构。

返回相对路径列表（使用正斜杠分隔），Agent 可直接用作其他工具的 path 参数。
"""

import os
from pathlib import Path

from tools.base import Tool
from tools.security import HIDDEN_FILES, validate_path


class ListFilesTool(Tool):
    name = "list_files"
    description = (
        "List files and directories in the workspace. "
        "Returns relative paths (forward-slash separated) that can be used "
        "directly as arguments to other tools. "
        "Use this to explore what files exist before reading or searching them."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative path from workspace root to list. Defaults to workspace root.",
                "default": ".",
            },
            "recursive": {
                "type": "boolean",
                "description": "Whether to list recursively into subdirectories. Defaults to true.",
                "default": True,
            },
        },
        "required": [],
    }

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root

    def execute(self, path: str = ".", recursive: bool = True) -> str:
        target = validate_path(self.workspace_root, path)

        if not target.exists():
            return f"Error: Path '{path}' does not exist."
        if not target.is_dir():
            return f"Error: '{path}' is not a directory."

        entries: list[str] = []

        if recursive:
            for root, dirs, files in os.walk(target):
                # 过滤隐藏目录，排序保证输出稳定
                dirs[:] = sorted(d for d in dirs if not d.startswith("."))
                files = sorted(files)

                rel_root = os.path.relpath(root, target)
                for f in files:
                    if f in HIDDEN_FILES:
                        continue
                    if rel_root == ".":
                        entries.append(f)
                    else:
                        entries.append(f"{rel_root}/{f}")

                for d in dirs:
                    if rel_root == ".":
                        entries.append(f"{d}/")
                    else:
                        entries.append(f"{rel_root}/{d}/")
        else:
            for item in sorted(target.iterdir()):
                if item.name in HIDDEN_FILES or item.name.startswith("."):
                    continue
                suffix = "/" if item.is_dir() else ""
                entries.append(f"{item.name}{suffix}")

        if not entries:
            return f"Directory '{path}' is empty."

        return "\n".join(entries)
