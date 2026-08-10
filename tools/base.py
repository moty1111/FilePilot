"""
Tool 基类与注册表。

每个工具继承 Tool 基类，声明 name / description / parameters（JSON Schema），
并实现 execute() 方法。ToolRegistry 负责统一注册、查找和调度。
"""

from abc import ABC, abstractmethod
from typing import Any


class Tool(ABC):
    """工具基类。子类需设置 name、description、parameters 并实现 execute()。"""

    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = {}

    @abstractmethod
    def execute(self, **kwargs) -> str:
        """执行工具逻辑，返回字符串结果给 LLM。"""
        ...

    def get_schema(self) -> dict[str, Any]:
        """返回 OpenAI function calling 格式的工具定义。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    """工具注册表，管理所有可用工具的注册、查找和执行。"""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """注册一个工具实例。"""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        """按名称获取工具实例。"""
        return self._tools.get(name)

    def get_all_schemas(self) -> list[dict[str, Any]]:
        """返回所有工具的 schema 列表，用于传给 LLM。"""
        return [tool.get_schema() for tool in self._tools.values()]

    def execute(self, name: str, args: dict[str, Any]) -> str:
        """
        按名称执行工具。

        任何执行异常都会被捕获并转为错误字符串返回，
        确保 Agent Loop 不会因工具异常而崩溃。
        """
        tool = self.get(name)
        if tool is None:
            return f"Error: Unknown tool '{name}'."

        try:
            return tool.execute(**args)
        except ValueError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error executing tool '{name}': {e}"
