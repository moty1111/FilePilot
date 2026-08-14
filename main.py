"""
FastAPI 应用入口。

提供 Web API 供前端 Demo 调用，同时可作为 uvicorn 启动入口。

启动方式:
    uvicorn main:app --reload --port 8000
    或
    python main.py
"""

import atexit

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router as tasks_router
from api.routes import workspace_router
from service.agent_service import agent_service

app = FastAPI(
    title="FilePilot Agent",
    description="基于 LLM 的文件操作 Agent — 提交自然语言任务，Agent 自主调用工具完成",
    version="0.1.0",
)

# 允许前端跨域访问（Demo 用，生产环境应限制具体域名）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 API 路由
app.include_router(tasks_router)
app.include_router(workspace_router)


@app.on_event("shutdown")
async def shutdown() -> None:
    """应用关闭时清理线程池资源。"""
    agent_service.shutdown()


@app.get("/", summary="根路径")
async def root() -> dict:
    """服务信息。"""
    return {"status": "ok", "service": "FilePilot Agent", "docs": "/docs"}


@app.get("/health", summary="健康检查")
async def health() -> dict:
    """健康检查端点。"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
