"""
Agent API 数据模型定义。

定义 Web API 层使用的 Pydantic 请求/响应模型，
包括任务提交、任务状态查询、Trace 记录等。
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ─────────────────── 请求模型 ───────────────────


class TaskCreateRequest(BaseModel):
    """提交 Agent 任务的请求。"""

    task: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="自然语言任务指令",
        example="列出 workspace 中所有文件并总结其内容",
    )
    workspace_path: str | None = Field(
        None,
        description="自定义 workspace 路径（默认使用全局配置）",
        example=None,
    )
    max_steps: int | None = Field(
        None,
        ge=1,
        le=100,
        description="最大执行步数（默认使用全局配置）",
        example=20,
    )


# ─────────────────── 响应模型 ───────────────────


class TaskCreateResponse(BaseModel):
    """任务提交成功后的响应。"""

    task_id: str = Field(..., description="任务唯一标识")
    status: str = Field("pending", description="任务初始状态")
    created_at: str = Field(..., description="任务创建时间 (ISO 8601)")


class TokenUsage(BaseModel):
    """Token 用量统计。"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    total_calls: int = 0


class TaskStatusResponse(BaseModel):
    """任务状态与结果的完整信息。"""

    task_id: str = Field(..., description="任务唯一标识")
    task: str = Field(..., description="原始任务指令")
    status: str = Field(
        ..., description="任务状态: pending | running | completed | failed"
    )
    result: str | None = Field(None, description="Agent 最终回复（任务完成时填充）")
    error: str | None = Field(None, description="错误信息（任务失败时填充）")
    created_at: str = Field(..., description="任务创建时间 (ISO 8601)")
    completed_at: str | None = Field(None, description="任务完成时间 (ISO 8601)")
    workspace_path: str = Field(..., description="任务使用的 workspace 路径")
    token_usage: TokenUsage | None = Field(None, description="Token 用量统计")
    steps: int = Field(0, description="已执行的步数")


class TraceEntry(BaseModel):
    """单条 Trace 记录，对应 trace.jsonl 中的一行。"""

    step: int = Field(..., description="步骤编号")
    type: str = Field(
        ...,
        description="记录类型: llm_thinking | tool_call | final | max_steps_reached",
    )
    tool: str | None = Field(None, description="工具名称（tool_call 类型时）")
    args: dict[str, Any] | None = Field(None, description="工具参数")
    result_summary: str | None = Field(None, description="结果摘要")
    content: str | None = Field(None, description="LLM 思考内容（llm_thinking 类型时）")
    timestamp: str | None = Field(None, description="记录时间 (ISO 8601)")


class TraceResponse(BaseModel):
    """任务 Trace 记录列表。"""

    task_id: str = Field(..., description="任务唯一标识")
    traces: list[TraceEntry] = Field(default_factory=list, description="Trace 记录列表")


class TaskListItem(BaseModel):
    """任务列表中的单项摘要。"""

    task_id: str
    task: str
    status: str
    created_at: str
    completed_at: str | None = None


class TaskListResponse(BaseModel):
    """任务列表响应。"""

    tasks: list[TaskListItem] = Field(default_factory=list)
    total: int = Field(0, description="任务总数")


class ErrorResponse(BaseModel):
    """统一错误响应。"""

    detail: str = Field(..., description="错误描述")


# ─────────────────── Workspace 浏览模型 ───────────────────


class WorkspaceEntry(BaseModel):
    """workspace 目录树中的一项（文件或目录）。"""

    name: str = Field(..., description="文件/目录名")
    path: str = Field(..., description="相对 workspace 根目录的路径（正斜杠分隔）")
    type: str = Field(..., description="类型: directory | file")
    size: int | None = Field(None, description="文件大小（字节），仅文件有此字段")


class WorkspaceTreeResponse(BaseModel):
    """workspace 目录树响应。"""

    workspace_path: str = Field(..., description="workspace 根目录绝对路径")
    entries: list[WorkspaceEntry] = Field(
        default_factory=list, description="目录条目列表"
    )


class FileContentResponse(BaseModel):
    """workspace 文件内容响应。"""

    path: str = Field(..., description="相对 workspace 根目录的文件路径")
    name: str = Field(..., description="文件名")
    size: int = Field(..., description="文件大小（字节）")
    content: str = Field(..., description="文件文本内容（可能被截断）")
    truncated: bool = Field(False, description="内容是否因超过最大字符数而被截断")
    max_chars: int = Field(..., description="最大字符数限制")


class WorkspaceResetResponse(BaseModel):
    """workspace 重置操作响应。"""

    message: str = Field(..., description="操作结果描述")
    workspace_path: str = Field(..., description="工作目录路径")
    backup_path: str = Field(..., description="备份目录路径")
    restored_files: int = Field(..., description="恢复的文件数量")
