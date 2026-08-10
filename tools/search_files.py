"""
search_files 工具：在 workspace 中搜索关键词。

返回匹配的文件路径、行号和匹配行内容（截断到合理长度）。
结果数量上限为 max_results，避免返回过多内容。
"""

import os
from pathlib import Path

from tools.base import Tool
from tools.security import HIDDEN_FILES, validate_path


class SearchFilesTool(Tool):
    name = "search_files"
    description = (
        "Search for a keyword in all files within the workspace (or a subdirectory). "
        "Returns matching file paths, line numbers, and the matching line content. "
        "Search is case-insensitive. "
        "Use this to quickly find which files contain relevant information "
        "before reading them in full."
    )
    parameters = {
        "type": "object",
        "properties": {
            "keyword": {
                "type": "string",
                "description": "The keyword or phrase to search for (case-insensitive).",
            },
            "path": {
                "type": "string",
                "description": "Relative path to limit the search scope. Defaults to workspace root.",
                "default": ".",
            },
        },
        "required": ["keyword"],
    }

    def __init__(self, workspace_root: Path, max_results: int = 20) -> None:
        self.workspace_root = workspace_root
        self.max_results = max_results

    def execute(self, keyword: str, path: str = ".") -> str:
        target = validate_path(self.workspace_root, path)

        if not target.exists():
            return f"Error: Path '{path}' does not exist."

        keyword_lower = keyword.lower()
        results: list[str] = []

        # 收集要搜索的文件列表
        if target.is_file():
            files_to_search = [target]
        else:
            files_to_search = []
            for root, dirs, files in os.walk(target):
                dirs[:] = sorted(d for d in dirs if not d.startswith("."))
                for f in sorted(files):
                    if f in HIDDEN_FILES:
                        continue
                    files_to_search.append(Path(root) / f)

        # 逐文件搜索
        for file_path in files_to_search:
            if len(results) >= self.max_results:
                break

            rel_path = str(
                file_path.relative_to(self.workspace_root)
            ).replace("\\", "/")

            try:
                content = file_path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError):
                continue

            for i, line in enumerate(content.split("\n"), start=1):
                if keyword_lower in line.lower():
                    snippet = line.strip()
                    if len(snippet) > 200:
                        snippet = snippet[:200] + "..."
                    results.append(f"{rel_path}:{i}: {snippet}")
                    if len(results) >= self.max_results:
                        break

        if not results:
            return f"No matches found for '{keyword}'."

        header = f"Found {len(results)} match(es) for '{keyword}':\n"
        return header + "\n".join(results)
