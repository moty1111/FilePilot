"""
Agent API 路由定义。

暴露以下端点:
    POST   /api/tasks            - 提交 Agent 任务
    GET    /api/tasks            - 列出所有任务
    GET    /api/tasks/{task_id}  - 查询任务状态与结果
    GET    /api/tasks/{task_id}/trace - 获取任务 Trace 记录
    GET    /api/workspace             - 列出 workspace 目录树
    GET    /api/workspace/files/{path} - 读取 workspace 文件内容
    POST   /api/workspace/reset       - 重置 workspace 到初始状态
"""

import os
import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, status

from api.deps import agent_service
from core.config import settings
from schemas.agent import (
    FileContentResponse,
    TaskCreateRequest,
    TaskCreateResponse,
    TaskListItem,
    TaskListResponse,
    TaskStatusResponse,
    TraceEntry,
    TraceResponse,
    WorkspaceEntry,
    WorkspaceResetResponse,
    WorkspaceTreeResponse,
)
from tools.security import validate_path

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.post(
    "",
    response_model=TaskCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="提交 Agent 任务",
)
async def create_task(req: TaskCreateRequest) -> TaskCreateResponse:
    """
    提交一个自然语言任务，Agent 将在后台异步执行。

    立即返回 task_id，可通过 `GET /api/tasks/{task_id}` 轮询状态。
    """
    task_id = agent_service.submit_task(
        task=req.task,
        workspace_path=req.workspace_path,
        max_steps=req.max_steps,
    )
    record = agent_service.get_task_status(task_id)
    return TaskCreateResponse(
        task_id=task_id,
        status=record["status"],
        created_at=record["created_at"],
    )


@router.get(
    "",
    response_model=TaskListResponse,
    summary="列出所有任务",
)
async def list_tasks() -> TaskListResponse:
    """返回所有已提交任务的摘要列表，按创建时间降序排列。"""
    items = agent_service.list_tasks()
    return TaskListResponse(
        tasks=[TaskListItem(**item) for item in items],
        total=len(items),
    )


@router.get(
    "/{task_id}",
    response_model=TaskStatusResponse,
    summary="查询任务状态",
)
async def get_task(task_id: str) -> TaskStatusResponse:
    """
    查询指定任务的详细状态与结果。

    状态值: pending | running | completed | failed
    """
    record = agent_service.get_task_status(task_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_id}' not found.",
        )
    return TaskStatusResponse(**record)


@router.get(
    "/{task_id}/trace",
    response_model=TraceResponse,
    summary="获取任务 Trace",
)
async def get_task_trace(task_id: str) -> TraceResponse:
    """
    获取指定任务的 Trace 记录列表。

    每条记录对应 Agent 执行过程中的一步（工具调用、最终回复等）。
    """
    # 先检查任务是否存在
    record = agent_service.get_task_status(task_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_id}' not found.",
        )

    traces = agent_service.get_task_trace(task_id)
    if traces is None:
        traces = []

    return TraceResponse(
        task_id=task_id,
        traces=[TraceEntry(**t) for t in traces],
    )


# ─────────────────── Workspace 浏览 ───────────────────

workspace_router = APIRouter(prefix="/api/workspace", tags=["workspace"])


@workspace_router.get(
    "",
    response_model=WorkspaceTreeResponse,
    summary="列出 workspace 目录树",
)
async def list_workspace(
    path: str = Query(".", description="相对 workspace 根目录的子路径，默认为根目录"),
    recursive: bool = Query(False, description="是否递归列出所有子目录"),
) -> WorkspaceTreeResponse:
    """
    列出 workspace 中指定目录下的文件和子目录。

    与 Agent 内部的 `list_files` 工具不同，此端点**会显示** trace 文件
    （`trace_*.jsonl`），便于前端展示 Agent 的执行记录。
    """
    ws_root: Path = settings.workspace_path

    try:
        target = validate_path(ws_root, path)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )

    if not target.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Path '{path}' not found.",
        )
    if not target.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'{path}' is not a directory.",
        )

    def _rel(p: Path) -> str:
        """返回相对 workspace 根目录的路径（正斜杠分隔）。"""
        return str(p.relative_to(ws_root)).replace("\\", "/")

    entries: list[WorkspaceEntry] = []

    if recursive:
        for root, dirs, files in os.walk(target):
            # 过滤隐藏目录，原地修改 dirs 以阻止 os.walk 递归进入
            dirs[:] = sorted(d for d in dirs if not d.startswith("."))
            files = sorted(files)

            for d in dirs:
                full = Path(root) / d
                entries.append(
                    WorkspaceEntry(name=d, path=_rel(full), type="directory")
                )
            for f in files:
                full = Path(root) / f
                entries.append(
                    WorkspaceEntry(
                        name=f, path=_rel(full), type="file", size=full.stat().st_size
                    )
                )
    else:
        for item in sorted(target.iterdir()):
            if item.name.startswith("."):
                continue
            if item.is_dir():
                entries.append(
                    WorkspaceEntry(name=item.name, path=_rel(item), type="directory")
                )
            else:
                entries.append(
                    WorkspaceEntry(
                        name=item.name,
                        path=_rel(item),
                        type="file",
                        size=item.stat().st_size,
                    )
                )

    return WorkspaceTreeResponse(
        workspace_path=str(ws_root), entries=entries
    )


@workspace_router.get(
    "/files/{file_path:path}",
    response_model=FileContentResponse,
    summary="读取 workspace 文件内容",
)
async def read_workspace_file(file_path: str) -> FileContentResponse:
    """
    读取 workspace 中指定文件的文本内容。

    - 路径经过安全校验，防止目录逃逸。
    - 大文件内容会被截断至 `max_file_chars` 字符。
    - 非 UTF-8 文件（二进制）返回 422 错误。
    """
    ws_root: Path = settings.workspace_path

    try:
        full_path = validate_path(ws_root, file_path)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )

    if not full_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File '{file_path}' not found.",
        )
    if not full_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'{file_path}' is not a file.",
        )

    max_chars: int = settings.max_file_chars

    try:
        raw = full_path.read_bytes()
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"File '{file_path}' is not a valid UTF-8 text file (possibly binary).",
        )

    size: int = full_path.stat().st_size
    truncated: bool = len(content) > max_chars
    if truncated:
        content = content[:max_chars]

    return FileContentResponse(
        path=file_path.replace("\\", "/"),
        name=full_path.name,
        size=size,
        content=content,
        truncated=truncated,
        max_chars=max_chars,
    )


@workspace_router.post(
    "/reset",
    response_model=WorkspaceResetResponse,
    summary="重置 workspace 到初始状态",
)
async def reset_workspace() -> WorkspaceResetResponse:
    """
    将 workspace 重置为初始状态。

    从备份目录（workspace2）复制原始文件覆盖到工作目录（workspace），
    保留已有的 trace 文件。如果有任务正在运行则拒绝重置。
    """
    # 安全检查：有任务运行时禁止重置
    if agent_service.has_running_task():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="有任务正在运行，无法重置 workspace。请等待任务完成后再试。",
        )

    ws_root: Path = settings.workspace_path
    backup_root: Path = settings.backup_workspace_path

    if not backup_root.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"备份目录不存在: {backup_root}",
        )

    # 清空 workspace（保留 trace_*.jsonl 文件）
    for item in ws_root.iterdir():
        if item.is_dir():
            shutil.rmtree(item)
        elif item.is_file() and not item.name.startswith("trace_"):
            item.unlink()

    # 从备份目录复制全部内容
    shutil.copytree(backup_root, ws_root, dirs_exist_ok=True)

    # 统计恢复的文件数
    restored = sum(
        1
        for f in ws_root.rglob("*")
        if f.is_file() and not f.name.startswith("trace_")
    )

    return WorkspaceResetResponse(
        message="workspace 已重置为初始状态",
        workspace_path=str(ws_root),
        backup_path=str(backup_root),
        restored_files=restored,
    )
