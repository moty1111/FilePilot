"""
全局配置管理模块。

使用 python-dotenv 从 .env 文件加载环境变量，
通过 Settings 单例在整个项目中共享配置。
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 项目根目录（core/ 的上一级）
BASE_DIR = Path(__file__).resolve().parent.parent

# 加载 .env 文件
load_dotenv(BASE_DIR / ".env")


def _get_int(key: str, default: int) -> int:
    """从环境变量读取整数，失败则返回默认值。"""
    try:
        return int(os.getenv(key, default))
    except (TypeError, ValueError):
        return default


class Settings:
    """
    全局配置单例。

    所有配置项从环境变量读取，支持 .env 文件覆盖。
    在项目中通过 `from core.config import settings` 使用。
    """

    # --- LLM 配置 ---
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model_name: str = os.getenv("MODEL_NAME", "gpt-4o")

    # --- Agent 配置 ---
    max_steps: int = _get_int("MAX_STEPS", 20)

    # workspace 路径，支持相对路径（基于项目根目录）和绝对路径
    _workspace_raw: str = os.getenv("WORKSPACE_PATH", "./workspace")
    workspace_path: Path = (
        Path(_workspace_raw).resolve()
        if Path(_workspace_raw).is_absolute()
        else (BASE_DIR / _workspace_raw).resolve()
    )

    # workspace 备份路径（重置功能使用），支持相对路径和绝对路径
    _backup_ws_raw: str = os.getenv("BACKUP_WORKSPACE_PATH", "./workspace2")
    backup_workspace_path: Path = (
        Path(_backup_ws_raw).resolve()
        if Path(_backup_ws_raw).is_absolute()
        else (BASE_DIR / _backup_ws_raw).resolve()
    )

    # --- 安全配置（固定值，不从环境变量读取） ---
    # 单次 read_file 返回的最大字符数，防止大文件撑爆上下文窗口
    max_file_chars: int = 20000
    # search_files 返回的最大匹配条目数
    max_search_results: int = 20


# 全局单例
settings = Settings()
