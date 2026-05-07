"""后台任务管理器 — 管理项目生命周期和 Flow 执行"""

from __future__ import annotations

import asyncio
import logging
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any

from src.api.schemas import (
    ProjectBrief,
    ProjectDetail,
    ProjectStatus,
    StageProgress,
)
from src.flow.film_production_flow import FilmProductionFlow
from src.flow.state import FilmProjectState, StyleType

logger = logging.getLogger(__name__)


class ProjectRecord:
    """项目记录"""

    def __init__(
        self,
        project_id: str,
        prompt: str,
        style: str,
        duration: float,
        title: str | None = None,
        language: str = "zh",
    ):
        self.project_id = project_id
        self.prompt = prompt
        self.style = style
        self.duration = duration
        self.title = title
        self.language = language
        self.status = ProjectStatus.QUEUED
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.current_stage: str | None = None
        self.stages: list[StageProgress] = []
        self.video_path: str | None = None
        self.error: str | None = None
        self.quality_scores: dict[str, float | None] = {}
        self.flow_state: FilmProjectState | None = None
        self.cancelled = False


class TaskManager:
    """
    任务管理器
    
    负责：
    - 项目注册和生命周期管理
    - 后台执行 Flow
    - 状态查询和进度追踪
    - 取消和重试操作
    """

    def __init__(self, max_concurrent: int = 3):
        self._projects: dict[str, ProjectRecord] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._max_concurrent = max_concurrent

    @property
    def active_count(self) -> int:
        """当前活跃项目数"""
        return sum(
            1
            for p in self._projects.values()
            if p.status == ProjectStatus.RUNNING
        )

    @property
    def queue_size(self) -> int:
        """等待队列大小"""
        return sum(
            1
            for p in self._projects.values()
            if p.status == ProjectStatus.QUEUED
        )

    def create_project_id(self) -> str:
        """生成唯一项目 ID"""
        return str(uuid.uuid4())[:12]

    def register_project(
        self,
        project_id: str,
        prompt: str,
        style: str,
        duration: float,
        title: str | None = None,
        language: str = "zh",
    ) -> None:
        """注册新项目"""
        record = ProjectRecord(
            project_id=project_id,
            prompt=prompt,
            style=style,
            duration=duration,
            title=title,
            language=language,
        )
        # 初始化阶段列表
        record.stages = [
            StageProgress(stage_name="initialization", status="pending"),
            StageProgress(stage_name="screenplay", status="pending"),
            StageProgress(stage_name="asset_generation", status="pending"),
            StageProgress(stage_name="video_composition", status="pending"),
            StageProgress(stage_name="finalization", status="pending"),
        ]
        self._projects[project_id] = record

    async def run_project(self, project_id: str) -> None:
        """后台执行项目 Flow"""
        record = self._projects.get(project_id)
        if not record:
            logger.error(f"Project {project_id} not found")
            return

        async with self._semaphore:
            if record.cancelled:
                record.status = ProjectStatus.CANCELLED
                return

            record.status = ProjectStatus.RUNNING
            logger.info(f"Starting project: {project_id}")

            try:
                # 构建 Flow 初始状态
                initial_state = FilmProjectState(
                    user_prompt=record.prompt,
                    style_type=StyleType(record.style),
                    target_duration=record.duration,
                )

                flow = FilmProductionFlow(state=initial_state)
                record.flow_state = initial_state

                # 运行 Flow（同步操作，放在线程池中）
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, flow.kickoff)

                # 更新完成状态
                if record.cancelled:
                    record.status = ProjectStatus.CANCELLED
                else:
                    record.status = ProjectStatus.COMPLETED
                    record.video_path = initial_state.final_video_path

                    # 提取质量分数
                    if initial_state.screenplay_quality:
                        record.quality_scores["screenplay"] = (
                            initial_state.screenplay_quality.overall_score.score
                        )
                    if initial_state.asset_quality:
                        record.quality_scores["assets"] = (
                            initial_state.asset_quality.overall_score.score
                        )
                    if initial_state.final_quality:
                        record.quality_scores["final"] = (
                            initial_state.final_quality.overall_score.score
                        )

                    # 更新标题
                    if initial_state.screenplay and not record.title:
                        record.title = initial_state.screenplay.title

                    # 更新所有阶段为完成
                    for stage in record.stages:
                        stage.status = "completed"

                logger.info(f"Project completed: {project_id}")

            except Exception as e:
                record.status = ProjectStatus.FAILED
                record.error = f"{type(e).__name__}: {str(e)}"
                logger.error(
                    f"Project failed: {project_id}\n{traceback.format_exc()}"
                )

    async def retry_stage(
        self,
        project_id: str,
        stage: str,
        feedback: str | None = None,
    ) -> None:
        """重试指定阶段"""
        record = self._projects.get(project_id)
        if not record:
            return

        record.status = ProjectStatus.RUNNING
        logger.info(f"Retrying stage '{stage}' for project {project_id}")

        try:
            # 简化实现：重新运行整个 flow
            # 在生产环境中，应该只重运行指定阶段
            await self.run_project(project_id)
        except Exception as e:
            record.status = ProjectStatus.FAILED
            record.error = str(e)

    def cancel_project(self, project_id: str) -> bool:
        """取消项目"""
        record = self._projects.get(project_id)
        if not record:
            return False
        if record.status in (ProjectStatus.COMPLETED, ProjectStatus.CANCELLED):
            return False

        record.cancelled = True
        record.status = ProjectStatus.CANCELLED
        return True

    def get_project_detail(self, project_id: str) -> ProjectDetail | None:
        """获取项目详情"""
        record = self._projects.get(project_id)
        if not record:
            return None

        # 计算 screenplay summary
        screenplay_summary = None
        if record.flow_state and record.flow_state.screenplay:
            sp = record.flow_state.screenplay
            screenplay_summary = f"{sp.title}: {sp.logline}"

        return ProjectDetail(
            project_id=record.project_id,
            title=record.title,
            status=record.status,
            style=record.style,
            duration=record.duration,
            created_at=record.created_at,
            prompt=record.prompt,
            stages=record.stages,
            current_stage=record.current_stage,
            video_url=record.video_path,
            screenplay_summary=screenplay_summary,
            quality_scores=record.quality_scores,
            error=record.error,
        )

    def list_projects(
        self,
        page: int = 1,
        page_size: int = 20,
        status_filter: ProjectStatus | None = None,
    ) -> tuple[list[ProjectBrief], int]:
        """获取项目列表"""
        all_records = list(self._projects.values())

        # 过滤
        if status_filter:
            all_records = [r for r in all_records if r.status == status_filter]

        # 按创建时间倒序
        all_records.sort(key=lambda r: r.created_at, reverse=True)

        total = len(all_records)

        # 分页
        start = (page - 1) * page_size
        end = start + page_size
        page_records = all_records[start:end]

        briefs = []
        for r in page_records:
            # 计算进度百分比
            completed_stages = sum(1 for s in r.stages if s.status == "completed")
            progress = (completed_stages / len(r.stages) * 100) if r.stages else 0

            briefs.append(
                ProjectBrief(
                    project_id=r.project_id,
                    title=r.title,
                    status=r.status,
                    style=r.style,
                    duration=r.duration,
                    created_at=r.created_at,
                    progress_percent=progress,
                )
            )

        return briefs, total
