"""
Agent CLI 入口。

支持本地命令行运行，例如:
    python agent.py --workspace ./workspace --task "找出所有提到 Project Falcon 的文件"

输出 trace.jsonl 到当前目录，每步一行 JSON 记录。
"""

import argparse
import sys

from core.config import settings


def main() -> None:
    """CLI 主函数：解析参数，启动 Agent 执行任务。"""
    parser = argparse.ArgumentParser(description="FilePilot Agent - 文件操作 Agent")
    parser.add_argument(
        "--workspace",
        type=str,
        default=str(settings.workspace_path),
        help="workspace 目录路径（默认: ./workspace）",
    )
    parser.add_argument(
        "--task",
        type=str,
        required=True,
        help="自然语言任务指令",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=settings.max_steps,
        help=f"最大执行步数（默认: {settings.max_steps}）",
    )
    args = parser.parse_args()

    print(f"=== FilePilot Agent ===")
    print(f"Workspace: {args.workspace}")
    print(f"Task: {args.task}")
    print(f"Max steps: {args.max_steps}")
    print(f"Model: {settings.model_name}")
    print()

    # TODO: Phase 3 实现 Agent Loop 后，在此处启动 Agent
    # from agent.agent import AgentRunner
    # runner = AgentRunner(workspace_path=args.workspace, max_steps=args.max_steps)
    # result = runner.run(args.task)
    # print(result)

    print("[Phase 1] Agent Loop 尚未实现，请等待 Phase 3。")
    sys.exit(0)


if __name__ == "__main__":
    main()
