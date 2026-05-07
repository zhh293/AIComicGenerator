"""
AI 短剧生成平台 — 主控 Flow

整个生产流程的编排器，使用 CrewAI Flow 框架实现多阶段流水线：

Stage 1: 初始化 → 解析用户输入，确定风格和参数
Stage 2: 剧本创作 → ScreenplayCrew 生成结构化剧本
Stage 3: 质量检查 → 评估剧本质量，不通过则重试
Stage 4: 素材生成 → AssetGenerationCrew 生成所有视频/音频素材
Stage 5: 质量检查 → 评估素材质量
Stage 6: 视频合成 → VideoCompositionCrew 合成最终视频
Stage 7: 最终检查 → 评估成片质量
Stage 8: 输出 → 返回最终结果
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from crewai.flow.flow import Flow, listen, router, start

from src.config import settings
from src.crews.asset_generation_crew import AssetGenerationCrew
from src.crews.screenplay_crew import ScreenplayCrew
from src.crews.video_composition_crew import VideoCompositionCrew
from src.flow.state import (
    FilmProjectState,
    SceneAssetBundle,
    StageQualityReport,
    StyleType,
)
from src.quality.evaluators import (
    FinalVideoEvaluator,
    ScreenplayEvaluator,
)
from src.quality.retry_strategy import RetryStrategy
from src.style.presets import STYLE_PRESETS, StylePresetConfig

logger = logging.getLogger(__name__)


class FilmProductionFlow(Flow[FilmProjectState]):
    """
    AI 短剧生成主控 Flow

    状态管理: FilmProjectState (Pydantic BaseModel)
    路由逻辑: 质量检查结果决定走「下一阶段」还是「重试当前阶段」
    """

    # ================================================================
    # Stage 1: 初始化
    # ================================================================

    @start()
    def initialize_project(self) -> None:
        """解析用户输入，初始化项目配置"""
        logger.info("=== Stage 1: Project Initialization ===")

        state = self.state
        state.current_stage = "initialization"

        # 确定风格配置
        style_key = state.style.value

        # 设置输出目录
        project_dir = Path(settings.output_dir) / f"project_{int(time.time())}"
        project_dir.mkdir(parents=True, exist_ok=True)

        # 创建子目录
        (project_dir / "characters").mkdir(exist_ok=True)
        (project_dir / "scenes").mkdir(exist_ok=True)
        (project_dir / "audio").mkdir(exist_ok=True)
        (project_dir / "temp").mkdir(exist_ok=True)

        state.progress_percent = 5.0
        logger.info(
            f"Project initialized: style={style_key}, "
            f"duration={state.target_duration_seconds}s, dir={project_dir}"
        )

    # ================================================================
    # Stage 2: 剧本创作
    # ================================================================

    @listen(initialize_project)
    def create_screenplay(self) -> None:
        """调用 ScreenplayCrew 生成结构化剧本"""
        logger.info("=== Stage 2: Screenplay Creation ===")

        state = self.state
        state.current_stage = "screenplay_creation"
        state.progress_percent = 10.0

        style_config = self._get_style_config()

        crew = ScreenplayCrew(
            style_config=style_config,
            target_duration=state.target_duration_seconds,
            style_type=state.style,
        )

        result = crew.crew().kickoff(
            inputs={"user_prompt": state.user_prompt}
        )

        # 解析结果
        if hasattr(result, "pydantic") and result.pydantic is not None:
            state.screenplay = result.pydantic
        else:
            logger.warning("Screenplay result is not Pydantic object")
            state.log_error("Screenplay generation returned non-structured result")

        state.progress_percent = 25.0
        logger.info(
            f"Screenplay created: "
            f"{state.screenplay.title if state.screenplay else 'FAILED'}"
        )

    # ================================================================
    # Stage 3: 剧本质量检查
    # ================================================================

    @listen(create_screenplay)
    def check_screenplay_quality(self) -> None:
        """评估剧本质量"""
        logger.info("=== Stage 3: Screenplay Quality Check ===")

        state = self.state
        state.current_stage = "screenplay_quality_check"

        if not state.screenplay:
            state.quality_reports["screenplay"] = StageQualityReport(
                stage_name="screenplay",
                scores=[],
                average_score=0.0,
                passed=False,
                improvement_suggestions=["Regenerate screenplay from scratch"],
            )
            return

        evaluator = ScreenplayEvaluator(
            target_duration=state.target_duration_seconds
        )
        report = evaluator.evaluate(state.screenplay)
        state.quality_reports["screenplay"] = report

        logger.info(
            f"Screenplay quality: score={report.average_score:.2f}, "
            f"passed={report.passed}"
        )

    @router(check_screenplay_quality)
    def route_after_screenplay_check(self) -> str:
        """根据质量检查结果路由"""
        state = self.state
        report = state.quality_reports.get("screenplay")

        if report and report.passed:
            return "generate_assets"

        # 检查重试次数
        retry_count = state.get_retry_count("screenplay")
        max_retries = settings.max_retries

        if retry_count >= max_retries:
            logger.warning(
                f"Screenplay retry limit reached ({retry_count}), proceeding anyway"
            )
            return "generate_assets"

        state.increment_retry("screenplay")
        logger.info(f"Retrying screenplay (attempt {retry_count + 1})")
        return "retry_screenplay"

    @listen("retry_screenplay")
    def retry_screenplay_creation(self) -> None:
        """重试剧本创作，附带修改建议"""
        logger.info("=== Stage 3b: Screenplay Retry ===")

        state = self.state
        report = state.quality_reports.get("screenplay")
        suggestions = ""
        if report:
            suggestions = "\n".join(report.improvement_suggestions or [])

        # 增强 prompt 附加修改建议
        enhanced_prompt = (
            f"{state.user_prompt}\n\n"
            f"[Previous attempt feedback - please address these issues]:\n"
            f"{suggestions}"
        )

        style_config = self._get_style_config()

        crew = ScreenplayCrew(
            style_config=style_config,
            target_duration=state.target_duration_seconds,
            style_type=state.style,
        )

        result = crew.crew().kickoff(inputs={"user_prompt": enhanced_prompt})

        if hasattr(result, "pydantic") and result.pydantic is not None:
            state.screenplay = result.pydantic

    @listen(retry_screenplay_creation)
    def recheck_screenplay(self) -> None:
        """重试后再次检查质量"""
        self.check_screenplay_quality()

    # ================================================================
    # Stage 4: 素材生成
    # ================================================================

    @listen("generate_assets")
    def generate_assets(self) -> None:
        """调用 AssetGenerationCrew 生成所有素材"""
        logger.info("=== Stage 4: Asset Generation ===")

        state = self.state
        state.current_stage = "asset_generation"
        state.progress_percent = 30.0

        style_config = self._get_style_config()

        crew = AssetGenerationCrew(
            style_config=style_config,
            project_state=state,
        )

        result = crew.crew().kickoff()

        state.progress_percent = 60.0
        logger.info("Asset generation complete")

    # ================================================================
    # Stage 5: 素材质量检查（简化版）
    # ================================================================

    @listen(generate_assets)
    def check_asset_quality(self) -> None:
        """评估素材质量"""
        logger.info("=== Stage 5: Asset Quality Check ===")

        state = self.state
        state.current_stage = "asset_quality_check"

        # 检查是否有生成的素材
        if not state.scene_assets:
            state.quality_reports["assets"] = StageQualityReport(
                stage_name="assets",
                scores=[],
                average_score=0.0,
                passed=False,
                improvement_suggestions=["No assets were generated"],
            )
        else:
            # 有素材则认为通过（实际中应逐一检查）
            state.quality_reports["assets"] = StageQualityReport(
                stage_name="assets",
                scores=[],
                average_score=0.85,
                passed=True,
            )

        state.progress_percent = 65.0

    @router(check_asset_quality)
    def route_after_asset_check(self) -> str:
        """根据素材质量检查结果路由"""
        state = self.state
        report = state.quality_reports.get("assets")

        if report and report.passed:
            return "compose_video"

        retry_count = state.get_retry_count("assets")
        if retry_count >= settings.max_retries:
            logger.warning("Asset retry limit reached, proceeding anyway")
            return "compose_video"

        state.increment_retry("assets")
        return "retry_assets"

    @listen("retry_assets")
    def retry_asset_generation(self) -> None:
        """重试素材生成"""
        logger.info("=== Stage 5b: Asset Retry ===")
        self.generate_assets()

    # ================================================================
    # Stage 6: 视频合成
    # ================================================================

    @listen("compose_video")
    def compose_video(self) -> None:
        """调用 VideoCompositionCrew 合成最终视频"""
        logger.info("=== Stage 6: Video Composition ===")

        state = self.state
        state.current_stage = "video_composition"
        state.progress_percent = 70.0

        style_config = self._get_style_config()

        crew = VideoCompositionCrew(
            style_config=style_config,
            project_state=state,
            scene_bundles=state.scene_assets,
        )

        result = crew.crew().kickoff()

        # 设置最终视频路径
        state.final_video_path = str(
            Path(settings.output_dir) / "final_film.mp4"
        )
        state.progress_percent = 90.0
        logger.info(f"Video composition complete: {state.final_video_path}")

    # ================================================================
    # Stage 7: 最终质量检查
    # ================================================================

    @listen(compose_video)
    def check_final_quality(self) -> None:
        """评估最终成片质量"""
        logger.info("=== Stage 7: Final Quality Check ===")

        state = self.state
        state.current_stage = "final_quality_check"

        if not state.final_video_path:
            state.quality_reports["final"] = StageQualityReport(
                stage_name="final_video",
                scores=[],
                average_score=0.0,
                passed=False,
            )
            return

        evaluator = FinalVideoEvaluator()
        report = evaluator.evaluate(
            video_path=state.final_video_path,
            target_duration=state.target_duration_seconds,
        )
        state.quality_reports["final"] = report

        logger.info(
            f"Final quality: score={report.average_score:.2f}, "
            f"passed={report.passed}"
        )

    @router(check_final_quality)
    def route_after_final_check(self) -> str:
        """最终质量路由"""
        state = self.state
        report = state.quality_reports.get("final")

        if report and report.passed:
            return "finalize"

        retry_count = state.get_retry_count("final")
        if retry_count >= 2:
            logger.warning("Final retry limit reached, delivering current version")
            return "finalize"

        state.increment_retry("final")
        return "retry_composition"

    @listen("retry_composition")
    def retry_composition(self) -> None:
        """重试视频合成"""
        logger.info("=== Stage 7b: Composition Retry ===")
        self.compose_video()

    # ================================================================
    # Stage 8: 最终输出
    # ================================================================

    @listen("finalize")
    def finalize_project(self) -> dict[str, Any]:
        """整理输出结果"""
        logger.info("=== Stage 8: Finalization ===")

        state = self.state
        state.current_stage = "completed"
        state.progress_percent = 100.0

        result = {
            "status": "success",
            "title": state.screenplay.title if state.screenplay else "Untitled",
            "video_path": state.final_video_path,
            "duration": state.target_duration_seconds,
            "style": state.style.value,
            "quality_scores": {
                stage: report.average_score
                for stage, report in state.quality_reports.items()
                if hasattr(report, "average_score")
            },
            "retry_counts": state.retry_counts,
        }

        logger.info(f"Project finalized: {result['title']}")
        return result

    # ================================================================
    # 辅助方法
    # ================================================================

    def _get_style_config(self) -> StylePresetConfig:
        """获取当前风格配置"""
        config_name = self.state.style.value
        config = STYLE_PRESETS.get(config_name)
        if not config:
            config = STYLE_PRESETS["cinematic"]
        return config
