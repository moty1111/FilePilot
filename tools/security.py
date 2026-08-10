"""
路径安全校验模块。

所有涉及文件路径的工具在执行操作前，都必须通过此模块校验，
确保路径不会逃逸出 workspace 边界。
"""

from pathlib import Path

# 这些文件是基础设施产物，不应暴露给 Agent
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
