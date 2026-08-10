"""
FastAPI 应用入口。

提供 Web API 供前端 Demo 调用，同时可作为 uvicorn 启动入口。
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="FilePilot Agent",
    description="基于 LLM 的文件操作 Agent",
    version="0.1.0",
)

# 允许前端跨域访问（Demo 用，生产环境应限制具体域名）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root() -> dict:
    """健康检查端点。"""
    return {"status": "ok", "service": "FilePilot Agent"}


@app.get("/health")
async def health() -> dict:
    """健康检查。"""
    return {"status": "healthy"}
