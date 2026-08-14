"""
API 层依赖注入。

将 AgentService 单例暴露给路由使用，便于测试时替换 mock。
"""

from service.agent_service import agent_service

__all__ = ["agent_service"]
