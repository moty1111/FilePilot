"""
Agent 任务管理服务。

封装 AgentRunner，提供异步任务执行能力：
- 提交任务后立即返回 task_id，Agent 在后台线程执行
- 支持查询任务状态、结果、Trace 记录
- 内存中维护任务状态（适用于 Demo 场景）

线程模型:
    AgentRunner.run() 是同步阻塞调用（OpenAI SDK 为同步），
    通过 ThreadPoolExecutor 在后台线程执行，避免阻塞 FastAPI 事件循环。
"""

import json
import traceback
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent.agent import AgentRunner
from core.config import settings


def _utc_now_iso() -> str:
    """返回当前 UTC 时间的 ISO 8601 字符串。"""
    return datetime.now(timezone.utc).isoformat()


class TaskRecord:
    """单个任务的运行时状态记录（内存存储）。"""

    def __init__(
        self,
        task_id: str,
        task: str,
        workspace_path: str,
        max_steps: int,
    ) -> None:
        self.task_id = task_id
        self.task = task
        self.workspace_path = workspace_path
        self.max_steps = max_steps
        self.status: str = "pending"
        self.result: str | None = None
        self.error: str | None = None
        self.created_at: str = _utc_now_iso()
        self.completed_at: str | None = None
        self.token_usage: dict[str, int] | None = None
        self.steps: int = 0
        # 每个任务独立 trace 文件，便于隔离查询
        self.trace_path: Path = (
            Path(workspace_path) / f"trace_{task_id}.jsonl"
        )
        self._runner: AgentRunner | None = None

    def to_status_dict(self) -> dict[str, Any]:
        """转换为 TaskStatusResponse 所需的 dict。"""
        return {
            "task_id": self.task_id,
            "task": self.task,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "workspace_path": self.workspace_path,
            "token_usage": self.token_usage,
            "steps": self.steps,
        }


class AgentService:
    """
    Agent 任务管理服务。

    用法:
        service = AgentService()
        task_id = service.submit_task("找出所有提到 Project Falcon 的文件")
        status = service.get_task_status(task_id)
        trace = service.get_task_trace(task_id)
    """

    def __init__(self, max_workers: int = 4) -> None:
        """
        初始化 AgentService。

        Args:
            max_workers: 线程池最大并发数。
        """
        self._tasks: dict[str, TaskRecord] = {}
        self._futures: dict[str, Future] = {}
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="agent-worker"
        )

    def submit_task(
        self,
        task: str,
        workspace_path: str | None = None,
        max_steps: int | None = None,
    ) -> str:
        """
        提交一个 Agent 任务，返回 task_id。

        任务提交后立即返回，Agent 在后台线程异步执行。
        可通过 get_task_status() 轮询状态。

        Args:
            task: 自然语言任务指令。
            workspace_path: 自定义 workspace 路径，默认使用全局配置。
            max_steps: 最大执行步数，默认使用全局配置。

        Returns:
            任务唯一标识 task_id。
        """
        task_id = uuid.uuid4().hex[:12]
        ws = workspace_path or str(settings.workspace_path)
        steps = max_steps if max_steps is not None else settings.max_steps

        record = TaskRecord(task_id, task, ws, steps)
        self._tasks[task_id] = record

        # 提交到线程池异步执行
        future = self._executor.submit(self._run_task, task_id)
        self._futures[task_id] = future

        return task_id

    def _run_task(self, task_id: str) -> None:
        """
        在后台线程中执行 Agent 任务。

        注意: 此方法在 ThreadPoolExecutor 线程中运行，
        不能直接访问 FastAPI 的异步上下文。
        """
        record = self._tasks[task_id]
        record.status = "running"

        try:
            runner = AgentRunner(
                workspace_path=record.workspace_path,
                max_steps=record.max_steps,
                trace_path=record.trace_path,
            )
            record._runner = runner

            result = runner.run(record.task)

            record.result = result
            record.status = "completed"
            record.token_usage = runner.llm_client.get_total_usage()
            record.steps = runner.tracer.step
        except Exception as e:
            record.status = "failed"
            record.error = f"{type(e).__name__}: {e}"
            traceback.print_exc()
        finally:
            record.completed_at = _utc_now_iso()

    def get_task_status(self, task_id: str) -> dict[str, Any] | None:
        """
        查询任务状态。

        Args:
            task_id: 任务唯一标识。

        Returns:
            任务状态 dict，如果 task_id 不存在返回 None。
        """
        record = self._tasks.get(task_id)
        if record is None:
            return None
        return record.to_status_dict()

    def get_task_trace(self, task_id: str) -> list[dict[str, Any]] | None:
        """
        读取任务的 Trace 记录。

        从 trace_{task_id}.jsonl 文件逐行解析 JSON。

        Args:
            task_id: 任务唯一标识。

        Returns:
            Trace 记录列表，如果 task_id 不存在返回 None。
            任务尚未产生 trace 文件时返回空列表。
        """
        record = self._tasks.get(task_id)
        if record is None:
            return None

        if not record.trace_path.exists():
            return []

        traces: list[dict[str, Any]] = []
        for line in record.trace_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                traces.append(json.loads(line))
            except json.JSONDecodeError:
                continue

        return traces

    def has_running_task(self) -> bool:
        """检查是否有任务正在运行（pending 或 running 状态）。"""
        return any(
            r.status in ("pending", "running") for r in self._tasks.values()
        )

    def list_tasks(self) -> list[dict[str, Any]]:
        """返回所有任务的摘要列表（按创建时间降序）。"""
        items = [
            {
                "task_id": r.task_id,
                "task": r.task,
                "status": r.status,
                "created_at": r.created_at,
                "completed_at": r.completed_at,
            }
            for r in self._tasks.values()
        ]
        items.sort(key=lambda x: x["created_at"], reverse=True)
        return items

    def shutdown(self) -> None:
        """关闭线程池，等待所有任务完成。"""
        self._executor.shutdown(wait=True)


# 全局单例
agent_service = AgentService()
