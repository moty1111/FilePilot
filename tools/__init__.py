"""
tools 包：Agent 可用的文件操作工具集。

包含 5 个工具：
- list_files: 列出目录结构
- read_file: 读取文件内容（支持分块）
- search_files: 关键词搜索
- write_file: 写入文件
- move_file: 移动文件

使用 create_tool_registry() 工厂函数创建已注册所有工具的 ToolRegistry。
"""

from pathlib import Path

from tools.base import Tool, ToolRegistry
from tools.list_files import ListFilesTool
from tools.move_file import MoveFileTool
from tools.read_file import ReadFileTool
from tools.search_files import SearchFilesTool
from tools.write_file import WriteFileTool


def create_tool_registry(
    workspace_root: Path,
    max_file_chars: int = 20000,
    max_search_results: int = 20,
) -> ToolRegistry:
    """
    创建并返回包含所有工具的 ToolRegistry。

    Args:
        workspace_root: workspace 根目录路径。
        max_file_chars: read_file 单次返回的最大字符数。
        max_search_results: search_files 返回的最大匹配数。

    Returns:
        已注册所有工具的 ToolRegistry 实例。
    """
    registry = ToolRegistry()
    registry.register(ListFilesTool(workspace_root))
    registry.register(ReadFileTool(workspace_root, max_file_chars))
    registry.register(SearchFilesTool(workspace_root, max_search_results))
    registry.register(WriteFileTool(workspace_root))
    registry.register(MoveFileTool(workspace_root))
    return registry


__all__ = [
    "Tool",
    "ToolRegistry",
    "create_tool_registry",
    "ListFilesTool",
    "ReadFileTool",
    "SearchFilesTool",
    "WriteFileTool",
    "MoveFileTool",
]
