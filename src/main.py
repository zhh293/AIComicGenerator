"""
AI 短剧生成平台 — FastAPI 服务入口

启动方式:
    uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

API 文档:
    - Swagger UI: http://localhost:8000/docs
    - ReDoc: http://localhost:8000/redoc
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api import routes
from src.api.task_manager import TaskManager
from src.config import settings

# ================================================================
# 日志配置
# ================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ================================================================
# 应用生命周期
# ================================================================


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期管理"""
    # Startup
    logger.info("=" * 60)
    logger.info("AI Film Studio - Starting up")
    logger.info(f"  OpenAI Model: {settings.openai_model_name}")
    logger.info(f"  Video Provider: {settings.video_api_provider}")
    logger.info(f"  Output Dir: {settings.output_dir}")
    logger.info(f"  Max Concurrent Projects: {settings.max_concurrent_projects}")
    logger.info("=" * 60)

    # 初始化任务管理器
    task_mgr = TaskManager(max_concurrent=settings.max_concurrent_projects)
    routes.task_manager = task_mgr

    yield

    # Shutdown
    logger.info("AI Film Studio - Shutting down")


# ================================================================
# FastAPI 应用
# ================================================================

app = FastAPI(
    title="AI Film Studio",
    description=(
        "AI 短剧生成平台 API\n\n"
        "通过多 Agent 协作实现从文字创意到完整短片的全自动生产。\n\n"
        "核心流程: 用户输入 → 剧本创作 → 素材生成 → 视频合成 → 成片输出"
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS 中间件（开发环境全开放，生产环境应限制）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(routes.router, prefix="/api/v1")


# ================================================================
# 根路由
# ================================================================


@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    """服务根路径"""
    return {
        "service": "AI Film Studio",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/api/v1/health",
    }


# ================================================================
# 直接运行支持
# ================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
