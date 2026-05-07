"""API 路由定义"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from src.api.schemas import (
    CreateProjectRequest,
    CreateProjectResponse,
    HealthResponse,
    ProjectDetail,
    ProjectListResponse,
    ProjectStatus,
    RetryStageRequest,
)
from src.api.task_manager import TaskManager

logger = logging.getLogger(__name__)

router = APIRouter()

# 全局任务管理器实例（由 main.py 注入）
task_manager: TaskManager | None = None


def get_task_manager() -> TaskManager:
    """获取任务管理器"""
    if task_manager is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return task_manager


# ================================================================
# 健康检查
# ================================================================


@router.get("/health", response_model=HealthResponse, tags=["system"])
async def health_check() -> HealthResponse:
    """服务健康检查"""
    mgr = get_task_manager()
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        active_projects=mgr.active_count,
        queue_size=mgr.queue_size,
    )


# ================================================================
# 项目 CRUD
# ================================================================


@router.post(
    "/projects",
    response_model=CreateProjectResponse,
    status_code=201,
    tags=["projects"],
)
async def create_project(
    request: CreateProjectRequest,
    background_tasks: BackgroundTasks,
) -> CreateProjectResponse:
    """
    创建新的 AI 短剧生成项目

    提交用户创意描述后，系统将自动启动完整的制作流水线：
    剧本创作 -> 素材生成 -> 视频合成
    """
    mgr = get_task_manager()

    project_id = mgr.create_project_id()

    # 注册项目
    mgr.register_project(
        project_id=project_id,
        prompt=request.prompt,
        style=request.style.value,
        duration=request.duration,
        title=request.title,
        language=request.language,
    )

    # 后台启动 Flow
    background_tasks.add_task(mgr.run_project, project_id)

    logger.info(f"Project created: {project_id}")
    return CreateProjectResponse(
        project_id=project_id,
        status=ProjectStatus.QUEUED,
        message=f"Project {project_id} created. Processing will begin shortly.",
    )


@router.get("/projects", response_model=ProjectListResponse, tags=["projects"])
async def list_projects(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: ProjectStatus | None = None,
) -> ProjectListResponse:
    """获取项目列表"""
    mgr = get_task_manager()
    projects, total = mgr.list_projects(
        page=page, page_size=page_size, status_filter=status
    )
    return ProjectListResponse(
        projects=projects,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/projects/{project_id}",
    response_model=ProjectDetail,
    tags=["projects"],
)
async def get_project(project_id: str) -> ProjectDetail:
    """获取项目详情"""
    mgr = get_task_manager()
    detail = mgr.get_project_detail(project_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return detail


@router.delete("/projects/{project_id}", tags=["projects"])
async def cancel_project(project_id: str) -> dict[str, str]:
    """取消正在进行的项目"""
    mgr = get_task_manager()
    success = mgr.cancel_project(project_id)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Project {project_id} not found or already completed",
        )
    return {"message": f"Project {project_id} cancelled"}


# ================================================================
# 项目操作
# ================================================================


@router.post("/projects/{project_id}/retry", tags=["projects"])
async def retry_stage(
    project_id: str,
    request: RetryStageRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    """手动触发某阶段的重试"""
    mgr = get_task_manager()
    project = mgr.get_project_detail(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    if project.status == ProjectStatus.RUNNING:
        raise HTTPException(
            status_code=409, detail="Project is currently running, cannot retry"
        )

    background_tasks.add_task(
        mgr.retry_stage, project_id, request.stage, request.feedback
    )
    return {"message": f"Retry initiated for stage '{request.stage}'"}


@router.get("/projects/{project_id}/download", tags=["projects"])
async def get_download_url(project_id: str) -> dict[str, Any]:
    """获取成片下载地址"""
    mgr = get_task_manager()
    detail = mgr.get_project_detail(project_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    if detail.status != ProjectStatus.COMPLETED or not detail.video_url:
        raise HTTPException(
            status_code=400,
            detail="Video not ready. Project must be completed first.",
        )

    return {
        "project_id": project_id,
        "video_url": detail.video_url,
        "title": detail.title,
    }


# ================================================================
# 系统 & 配置
# ================================================================


@router.get("/styles", tags=["config"])
async def list_styles() -> list[dict[str, str]]:
    """获取可用风格列表"""
    from src.style.presets import STYLE_PRESETS

    return [
        {
            "id": key,
            "name": config.display_name,
            "description": config.description,
        }
        for key, config in STYLE_PRESETS.items()
    ]
