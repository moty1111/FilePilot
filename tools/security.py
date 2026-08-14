"""
路径安全校验模块。

所有涉及文件路径的工具在执行操作前，都必须通过此模块校验，
确保路径不会逃逸出 workspace 边界。
"""

from pathlib import Path
import re

# trace 文件模式：trace.jsonl 和 trace_{task_id}.jsonl
_TRACE_PATTERN = re.compile(r"^trace(_.*)?\.jsonl$")


def is_hidden_file(name: str) -> bool:
    """
    判断文件是否应对 Agent 隐藏。

    基础设施产物（trace.jsonl、trace_{task_id}.jsonl）不应暴露给 Agent，
    避免 Agent 读取自身执行记录导致上下文混乱或 prompt injection。

    注意：此函数仅用于 Agent 内部工具过滤。Web API 的 workspace 浏览器
    不调用此函数，因此 trace 文件对前端可见，便于展示工具调用流程。

    Args:
        name: 文件名（不含路径）。

    Returns:
        True 表示该文件应对 Agent 隐藏。
    """
    return bool(_TRACE_PATTERN.match(name))


# 向后兼容：保留常量供可能的旧引用使用
HIDDEN_FILES = {"trace.jsonl"}


def validate_path(workspace_root: Path, relative_path: str) -> Path:
    """
    将相对路径解析为 workspace 内的绝对路径，并校验边界安全。

    Args:
        workspace_root: workspace 根目录的绝对路径。
        relative_path: 工具传入的相对路径（如 "meetings/xxx.md"）。

    Returns:
        解析后的绝对路径。

    Raises:
        ValueError: 如果路径解析后超出了 workspace 边界（如 ../../ 攻击）。
    """
    workspace_root = workspace_root.resolve()
    full_path = (workspace_root / relative_path).resolve()

    try:
        full_path.relative_to(workspace_root)
    except ValueError:
        raise ValueError(
            f"Path '{relative_path}' resolves outside the workspace boundary. "
            f"Access denied."
        )

    return full_path
