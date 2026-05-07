"""API 请求/响应数据模型"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ProjectStatus(str, Enum):
    """项目状态枚举"""

    QUEUED = "queued"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"  # 剧本待确认
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StyleOption(str, Enum):
    """可选风格"""

    CINEMATIC = "cinematic"
    ANIME = "anime"
    CYBERPUNK = "cyberpunk"
    INK_WASH = "ink_wash"
    REALISTIC = "realistic"


# ================================================================
# 请求模型
# ================================================================


class CreateProjectRequest(BaseModel):
    """创建项目请求"""

    prompt: str = Field(
        ...,
        min_length=10,
        max_length=5000,
        description="用户描述的故事内容/创意",
        examples=["一个孤独的机器人在废弃城市中寻找最后一朵花的故事"],
    )
    style: StyleOption = Field(
        default=StyleOption.CINEMATIC,
        description="视觉风格选择",
    )
    duration: float = Field(
        default=60.0,
        ge=15.0,
        le=180.0,
        description="目标时长（秒），范围 15-180",
    )
    title: Optional[str] = Field(
        default=None,
        max_length=100,
        description="自定义标题（可选，不填则由 AI 生成）",
    )
    language: str = Field(
        default="zh",
        description="语言代码（zh/en/ja 等）",
    )
    auto_approve: bool = Field(
        default=True,
        description="是否自动通过剧本审核。设为 false 则剧本生成后暂停等待人工确认",
    )


class RetryStageRequest(BaseModel):
    """手动重试某阶段"""

    stage: str = Field(
        ...,
        description="要重试的阶段名称",
        examples=["screenplay", "assets", "composition"],
    )
    feedback: Optional[str] = Field(
        default=None,
        description="附加的人工反馈/修改建议",
    )


# ================================================================
# 响应模型
# ================================================================


class ProjectBrief(BaseModel):
    """项目概要（列表页用）"""

    project_id: str
    title: Optional[str] = None
    status: ProjectStatus
    style: str
    duration: float
    created_at: str
    progress_percent: float = 0.0


class StageProgress(BaseModel):
    """阶段进度"""

    stage_name: str
    status: str  # pending / running / completed / failed
    score: Optional[float] = None
    retry_count: int = 0
    message: Optional[str] = None


class ProjectDetail(BaseModel):
    """项目详情"""

    project_id: str
    title: Optional[str] = None
    status: ProjectStatus
    style: str
    duration: float
    created_at: str
    prompt: str
    stages: List[StageProgress] = []
    current_stage: Optional[str] = None
    video_url: Optional[str] = None
    screenplay_summary: Optional[str] = None
    quality_scores: Dict[str, Optional[float]] = {}
    error: Optional[str] = None


class CreateProjectResponse(BaseModel):
    """创建项目响应"""

    project_id: str
    status: ProjectStatus = ProjectStatus.QUEUED
    message: str = "Project created and queued for processing"


class ProjectListResponse(BaseModel):
    """项目列表响应"""

    projects: List[ProjectBrief]
    total: int
    page: int = 1
    page_size: int = 20


class HealthResponse(BaseModel):
    """健康检查响应"""

    status: str = "healthy"
    version: str
    active_projects: int = 0
    queue_size: int = 0
