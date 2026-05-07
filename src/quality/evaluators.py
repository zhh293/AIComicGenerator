"""质量评估器 — 对各阶段产出进行多维度评估"""

from __future__ import annotations

import json
from typing import List, Optional

from loguru import logger

from src.config import settings
from src.flow.state import (
    Character,
    GeneratedVideoAsset,
    QualityScore,
    Screenplay,
    StageQualityReport,
)


class ScreenplayEvaluator:
    """
    剧本质量评估器
    
    评估维度：
    - 逻辑连贯性：情节因果关系是否合理
    - 情感弧线：是否有完整的情感起伏
    - 时长合理性：总时长是否接近目标
    - 场景可视化：场景描述是否足够具体
    - 角色完整性：角色描述是否充分支撑一致性
    """

    def __init__(self, target_duration: float):
        self.target_duration = target_duration

    def evaluate(self, screenplay: Screenplay) -> StageQualityReport:
        """执行完整评估"""
        scores = []

        # 1. 时长合理性（硬指标，可量化）
        duration_score = self._evaluate_duration_fit(screenplay)
        scores.append(duration_score)

        # 2. 场景完整性
        scene_score = self._evaluate_scene_completeness(screenplay)
        scores.append(scene_score)

        # 3. 角色描述充分性
        char_score = self._evaluate_character_completeness(screenplay)
        scores.append(char_score)

        # 4. 结构合理性
        structure_score = self._evaluate_structure(screenplay)
        scores.append(structure_score)

        # 5. 场景可视化程度
        visual_score = self._evaluate_visual_clarity(screenplay)
        scores.append(visual_score)

        # 计算综合分
        avg_score = sum(s.score for s in scores) / len(scores)
        passed = avg_score >= settings.quality_threshold_screenplay

        # 生成改进建议
        suggestions = [s.feedback for s in scores if s.score < 0.8 and s.feedback]

        report = StageQualityReport(
            stage_name="screenplay",
            scores=scores,
            average_score=avg_score,
            passed=passed,
            improvement_suggestions=suggestions,
        )

        logger.info(
            f"剧本评估完成: 平均分 {avg_score:.2f}, "
            f"{'通过' if passed else '未通过'}"
        )
        return report

    def _evaluate_duration_fit(self, screenplay: Screenplay) -> QualityScore:
        """评估时长合理性"""
        actual = screenplay.total_duration_seconds
        deviation = abs(actual - self.target_duration) / self.target_duration

        # 偏差 0% = 1.0, 偏差 20% = 0.8, 偏差 50% = 0.5
        score = max(0.0, 1.0 - deviation)

        feedback = ""
        if deviation > 0.15:
            diff = actual - self.target_duration
            direction = "长" if diff > 0 else "短"
            feedback = f"总时长偏差过大（{direction}{abs(diff):.1f}秒），请调整场景数量或单场景时长"

        return QualityScore(dimension="duration_fit", score=score, feedback=feedback)

    def _evaluate_scene_completeness(self, screenplay: Screenplay) -> QualityScore:
        """评估场景完整性"""
        issues = []
        total_scenes = len(screenplay.scenes)

        if total_scenes == 0:
            return QualityScore(
                dimension="scene_completeness",
                score=0.0,
                feedback="剧本无场景",
            )

        incomplete = 0
        for scene in screenplay.scenes:
            if not scene.environment_description:
                incomplete += 1
                issues.append(f"Scene {scene.scene_id}: 缺少环境描述")
            if not scene.visual_prompt:
                incomplete += 1
                issues.append(f"Scene {scene.scene_id}: 缺少视觉 Prompt")
            if scene.duration_seconds <= 0:
                incomplete += 1
                issues.append(f"Scene {scene.scene_id}: 时长无效")

        score = max(0.0, 1.0 - incomplete / (total_scenes * 3))
        feedback = "; ".join(issues[:3]) if issues else ""

        return QualityScore(dimension="scene_completeness", score=score, feedback=feedback)

    def _evaluate_character_completeness(self, screenplay: Screenplay) -> QualityScore:
        """评估角色描述充分性"""
        if not screenplay.characters:
            return QualityScore(
                dimension="character_completeness",
                score=0.5,
                feedback="无角色定义",
            )

        issues = []
        for char in screenplay.characters:
            if not char.appearance.hair_color:
                issues.append(f"{char.name}: 缺少发色")
            if not char.appearance.eye_color:
                issues.append(f"{char.name}: 缺少瞳色")
            if not char.outfit.main_clothing:
                issues.append(f"{char.name}: 缺少服装描述")

        total_checks = len(screenplay.characters) * 3
        score = max(0.0, 1.0 - len(issues) / total_checks) if total_checks > 0 else 0.5
        feedback = "; ".join(issues[:3]) if issues else ""

        return QualityScore(
            dimension="character_completeness", score=score, feedback=feedback
        )

    def _evaluate_structure(self, screenplay: Screenplay) -> QualityScore:
        """评估结构合理性"""
        score = 1.0
        issues = []

        # 检查是否有幕结构
        if not screenplay.acts:
            score -= 0.2
            issues.append("缺少幕结构划分")

        # 检查场景数量合理性（按时长估算）
        expected_scenes = max(3, int(self.target_duration / 8))  # 平均每场景 8 秒
        actual_scenes = len(screenplay.scenes)
        if actual_scenes < expected_scenes * 0.5:
            score -= 0.2
            issues.append(f"场景数过少（{actual_scenes}个，预期约{expected_scenes}个）")
        elif actual_scenes > expected_scenes * 2:
            score -= 0.1
            issues.append(f"场景数过多（{actual_scenes}个），可能过于碎片化")

        # 检查是否有 logline
        if not screenplay.logline:
            score -= 0.1
            issues.append("缺少一句话概述")

        score = max(0.0, score)
        feedback = "; ".join(issues) if issues else ""

        return QualityScore(dimension="structure", score=score, feedback=feedback)

    def _evaluate_visual_clarity(self, screenplay: Screenplay) -> QualityScore:
        """评估场景视觉描述的清晰度"""
        if not screenplay.scenes:
            return QualityScore(dimension="visual_clarity", score=0.0, feedback="无场景")

        low_quality_prompts = 0
        for scene in screenplay.scenes:
            # 检查 visual_prompt 的丰富程度（简单用长度衡量）
            if len(scene.visual_prompt) < 50:
                low_quality_prompts += 1

        score = max(0.0, 1.0 - low_quality_prompts / len(screenplay.scenes))
        feedback = ""
        if low_quality_prompts > 0:
            feedback = f"{low_quality_prompts}个场景的视觉描述过于简短，需要更具体的画面描述"

        return QualityScore(dimension="visual_clarity", score=score, feedback=feedback)


class VisualAssetEvaluator:
    """视觉素材质量评估器"""

    def __init__(self, consistency_threshold: float = 0.75):
        self.consistency_threshold = consistency_threshold

    def evaluate_single_scene(
        self,
        video_asset: GeneratedVideoAsset,
        character_similarity_scores: Optional[List[float]] = None,
    ) -> StageQualityReport:
        """评估单个场景的视觉素材质量"""
        scores = []

        # 1. 视频基础检查（文件存在、时长合理）
        basic_score = self._check_basic_validity(video_asset)
        scores.append(basic_score)

        # 2. 角色一致性（如果有 CLIP 分数）
        if character_similarity_scores:
            avg_sim = sum(character_similarity_scores) / len(character_similarity_scores)
            passed_consistency = avg_sim >= self.consistency_threshold
            scores.append(
                QualityScore(
                    dimension="character_consistency",
                    score=avg_sim,
                    feedback="" if passed_consistency else (
                        f"角色一致性不足（{avg_sim:.2f} < {self.consistency_threshold}），"
                        "建议增强参考图权重后重新生成"
                    ),
                )
            )

        avg_score = sum(s.score for s in scores) / len(scores)
        passed = avg_score >= settings.quality_threshold_visual

        return StageQualityReport(
            stage_name=f"visual_scene_{video_asset.scene_id}",
            scores=scores,
            average_score=avg_score,
            passed=passed,
            improvement_suggestions=[s.feedback for s in scores if s.feedback],
        )

    def _check_basic_validity(self, video_asset: GeneratedVideoAsset) -> QualityScore:
        """基础有效性检查"""
        from pathlib import Path

        issues = []

        if not Path(video_asset.video_path).exists():
            return QualityScore(
                dimension="basic_validity",
                score=0.0,
                feedback="视频文件不存在",
            )

        # 检查时长
        if video_asset.duration_seconds <= 0:
            issues.append("视频时长为0")
        elif video_asset.duration_seconds < 2:
            issues.append("视频时长过短（<2s）")

        score = 1.0 - len(issues) * 0.5
        return QualityScore(
            dimension="basic_validity",
            score=max(0.0, score),
            feedback="; ".join(issues),
        )


class AudioAssetEvaluator:
    """音频素材质量评估器"""

    def evaluate(self, audio_path: str, expected_duration: float = 0) -> StageQualityReport:
        """评估音频质量"""
        from pathlib import Path

        scores = []

        # 文件存在性
        if not Path(audio_path).exists():
            return StageQualityReport(
                stage_name="audio",
                scores=[QualityScore(dimension="existence", score=0.0, feedback="文件不存在")],
                average_score=0.0,
                passed=False,
            )

        # 文件大小检查（非空）
        file_size = Path(audio_path).stat().st_size
        if file_size < 1000:  # 小于 1KB 可能是空文件
            scores.append(
                QualityScore(dimension="file_validity", score=0.0, feedback="音频文件过小，可能损坏")
            )
        else:
            scores.append(QualityScore(dimension="file_validity", score=1.0, feedback=""))

        avg_score = sum(s.score for s in scores) / len(scores) if scores else 0
        return StageQualityReport(
            stage_name="audio",
            scores=scores,
            average_score=avg_score,
            passed=avg_score >= settings.quality_threshold_audio,
        )


class FinalVideoEvaluator:
    """最终视频质量评估器"""

    def evaluate(
        self,
        video_path: str,
        target_duration: float,
        tolerance: float = 0.1,
    ) -> StageQualityReport:
        """评估最终合成视频"""
        from pathlib import Path

        scores = []

        if not Path(video_path).exists():
            return StageQualityReport(
                stage_name="final_video",
                scores=[QualityScore(dimension="existence", score=0.0, feedback="最终视频不存在")],
                average_score=0.0,
                passed=False,
            )

        # 使用 FFprobe 检查视频信息
        try:
            from src.tools.ffmpeg_tools import FFmpegProbeTool

            probe = FFmpegProbeTool()
            info = json.loads(probe._run(file_path=video_path))

            # 时长检查
            actual_duration = info.get("duration_seconds", 0)
            duration_deviation = abs(actual_duration - target_duration) / target_duration

            duration_score = max(0.0, 1.0 - duration_deviation / tolerance)
            feedback = ""
            if duration_deviation > tolerance:
                feedback = (
                    f"时长偏差 {duration_deviation*100:.1f}% "
                    f"(实际 {actual_duration:.1f}s vs 目标 {target_duration:.1f}s)"
                )
            scores.append(QualityScore(dimension="duration", score=duration_score, feedback=feedback))

            # 分辨率检查
            video_info = info.get("video", {})
            if video_info:
                width = video_info.get("width", 0)
                height = video_info.get("height", 0)
                if width >= 1920 and height >= 1080:
                    scores.append(QualityScore(dimension="resolution", score=1.0, feedback=""))
                elif width >= 1280:
                    scores.append(
                        QualityScore(
                            dimension="resolution",
                            score=0.8,
                            feedback=f"分辨率偏低: {width}x{height}",
                        )
                    )
                else:
                    scores.append(
                        QualityScore(
                            dimension="resolution",
                            score=0.5,
                            feedback=f"分辨率过低: {width}x{height}",
                        )
                    )

            # 音频检查
            if info.get("audio"):
                scores.append(QualityScore(dimension="audio_track", score=1.0, feedback=""))
            else:
                scores.append(
                    QualityScore(
                        dimension="audio_track", score=0.5, feedback="视频无音频轨"
                    )
                )

        except Exception as e:
            logger.error(f"视频探测失败: {e}")
            scores.append(
                QualityScore(dimension="probe", score=0.5, feedback=f"探测失败: {str(e)}")
            )

        avg_score = sum(s.score for s in scores) / len(scores) if scores else 0
        return StageQualityReport(
            stage_name="final_video",
            scores=scores,
            average_score=avg_score,
            passed=avg_score >= 0.7,
            improvement_suggestions=[s.feedback for s in scores if s.feedback],
        )
