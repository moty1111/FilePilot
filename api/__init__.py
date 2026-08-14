"""
api 包：FastAPI 路由与依赖注入。
"""

from api.deps import agent_service
from api.routes import router

__all__ = ["router", "agent_service"]
