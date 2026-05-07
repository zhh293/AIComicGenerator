"""视频合成 Crew — 将素材片段合成为最终短片"""

from __future__ import annotations

from crewai import Agent, Crew, Process, Task

from src.config import settings
from src.emotion.curve import EmotionCurve, EmotionPoint, EmotionQuantizer
from src.emotion.mapper import EmotionToParamsMapper
from src.flow.state import FilmProjectState, SceneAssetBundle
from src.llm import get_llm
from src.style.presets import StylePresetConfig
from src.tools.ffmpeg_tools import (
    FFmpegAudioMixTool,
    FFmpegColorGradeTool,
    FFmpegConcatTool,
    FFmpegFrameExtractTool,
    FFmpegProbeTool,
    FFmpegSubtitleTool,
)


class VideoCompositionCrew:
    """
    视频合成 Crew
    
    包含三个 Agent：
    1. 视频剪辑师 — 负责片段拼接、转场和节奏控制
    2. 音频混音师 — 负责音频轨道混合和时间对齐
    3. 调色师 — 负责全片色彩统一和风格化处理
    
    最终输出一个完整的 MP4 成片
    """

    def __init__(
        self,
        style_config: StylePresetConfig,
        project_state: FilmProjectState,
        scene_bundles: list[SceneAssetBundle],
    ):
        self.style_config = style_config
        self.project_state = project_state
        self.scene_bundles = scene_bundles
        self._llm = get_llm()

        # 工具实例
        self._concat_tool = FFmpegConcatTool()
        self._audio_mix_tool = FFmpegAudioMixTool()
        self._subtitle_tool = FFmpegSubtitleTool()
        self._color_grade_tool = FFmpegColorGradeTool()
        self._probe_tool = FFmpegProbeTool()
        self._frame_tool = FFmpegFrameExtractTool()

    def crew(self) -> Crew:
        """组装并返回 Crew 实例"""
        return Crew(
            agents=[
                self._video_editor(),
                self._audio_mixer(),
                self._colorist(),
            ],
            tasks=[
                self._analyze_footage_task(),
                self._video_assembly_task(),
                self._audio_mixing_task(),
                self._subtitle_task(),
                self._color_grading_task(),
                self._final_export_task(),
            ],
            process=Process.sequential,
            verbose=True,
        )

    # ================================================================
    # Agent 定义
    # ================================================================

    def _video_editor(self) -> Agent:
        return Agent(
            role="视频剪辑师 (Video Editor)",
            goal=(
                "将各场景视频片段按剧本顺序拼接成完整影片，"
                "精确控制转场效果和剪辑节奏，确保叙事流畅。"
            ),
            backstory=(
                "你是好莱坞级别的剪辑师，擅长非线性叙事和节奏把控。"
                "你深知'剪辑就是电影的再创作'——通过合适的切点和转场，"
                "能让普通的素材变得引人入胜。你精通 FFmpeg 的各种滤镜和特效，"
                "善于利用转场来强化情绪转换。"
                "你的原则：每一次剪切都要有目的——"
                "要么推动叙事，要么强化情绪，要么建立节奏。"
            ),
            tools=[
                self._concat_tool,
                self._probe_tool,
                self._frame_tool,
            ],
            llm=self._llm,
            verbose=True,
        )

    def _audio_mixer(self) -> Agent:
        return Agent(
            role="音频混音师 (Audio Mixer)",
            goal=(
                "将配音、背景音乐、音效混合为层次分明的音频轨道。"
                "确保对话清晰可听，音乐烘托而不抢戏，整体音量平衡。"
            ),
            backstory=(
                "你是资深的影视混音师，有处理上百部短片音频的经验。"
                "你深知好的混音是'让观众忘记音频的存在'——"
                "一切都恰到好处、自然流畅。"
                "你精通音频工程：EQ 均衡、压缩、声像、混响、"
                "淡入淡出、ducking（对话时自动压低音乐）。"
                "你用 FFmpeg 的 amix、adelay、volume 等滤镜实现专业混音。"
            ),
            tools=[
                self._audio_mix_tool,
                self._probe_tool,
            ],
            llm=self._llm,
            verbose=True,
        )

    def _colorist(self) -> Agent:
        return Agent(
            role="调色师 (Colorist)",
            goal=(
                "对全片进行统一的色彩校正和风格化调色，"
                "确保不同场景在色彩层面看起来属于同一部影片。"
            ),
            backstory=(
                "你是经验丰富的调色师，理解色彩对情绪的深远影响。"
                f"你正在处理一部 {self.style_config.display_name} 风格的短片。"
                "你知道如何使用 LUT（色彩查找表）、曲线调整、"
                "色相/饱和度/亮度来创造统一且有辨识度的视觉风格。"
                "你的 FFmpeg 技能包含: curves, eq, hue, colorbalance, lut3d 等滤镜。"
            ),
            tools=[
                self._color_grade_tool,
                self._probe_tool,
                self._frame_tool,
            ],
            llm=self._llm,
            verbose=True,
        )

    # ================================================================
    # Task 定义
    # ================================================================

    def _analyze_footage_task(self) -> Task:
        """分析所有素材信息"""
        bundle_descriptions = []
        for bundle in self.scene_bundles:
            video_path = bundle.video.video_path if bundle.video else "N/A"
            audio_path = bundle.audio.dialogue_path if bundle.audio else "N/A"
            duration = bundle.video.duration_seconds if bundle.video else 0
            bundle_descriptions.append(
                f"- 场景 {bundle.scene_id}: "
                f"video={video_path}, "
                f"audio={audio_path}, "
                f"duration={duration}s"
            )
        bundles_text = "\n".join(bundle_descriptions)

        return Task(
            description=(
                "分析所有素材文件的技术参数，为后续合成做准备：\n\n"
                f"素材清单：\n{bundles_text}\n\n"
                "需要获取每个文件的：\n"
                "1. 分辨率、帧率、编码格式\n"
                "2. 精确时长\n"
                "3. 音频采样率、声道数\n"
                "4. 是否存在问题（损坏、格式不兼容等）\n\n"
                "输出一份完整的素材技术报告，标注需要预处理的文件。"
            ),
            expected_output="所有素材的技术参数报告和预处理建议",
            agent=self._video_editor(),
        )

    def _video_assembly_task(self) -> Task:
        """拼接视频片段"""
        screenplay = self.project_state.screenplay
        transitions = self.style_config.preferred_transitions

        scenes_info = []
        if screenplay:
            for scene in screenplay.scenes:
                scenes_info.append(
                    f"- {scene.scene_id}: 情绪={scene.mood}, "
                    f"转场建议={scene.transition_to_next or 'cut'}"
                )
        scenes_text = "\n".join(scenes_info)

        return Task(
            description=(
                "将所有视频片段按剧本顺序拼接为完整影片：\n\n"
                f"【场景序列和转场建议】\n{scenes_text}\n\n"
                f"【风格偏好转场】{transitions}\n\n"
                "拼接规则：\n"
                "1. 每两个场景之间根据情绪变化选择合适的转场\n"
                "   - 同一场景不同镜头：直切 (cut)\n"
                "   - 时间流逝或场景变换：渐溶 (dissolve, 0.5-1.0s)\n"
                "   - 情绪剧烈变化：淡入淡出 (fade, 0.8-1.5s)\n"
                "   - 动作连续：划入 (wipe) 或匹配剪辑\n"
                "2. 所有视频统一分辨率和帧率后再拼接\n"
                "3. 拼接顺序严格按剧本场景编号\n"
                "4. 输出中间文件供后续处理\n\n"
                "使用 FFmpeg concat + xfade 滤镜完成拼接。\n"
                "输出路径: {output_dir}/temp/assembled_raw.mp4"
            ),
            expected_output="拼接后的视频文件路径和总时长",
            agent=self._video_editor(),
        )

    def _audio_mixing_task(self) -> Task:
        """混合音频轨道"""
        return Task(
            description=(
                "将配音和背景音乐混合为最终音频轨道：\n\n"
                "混音方案：\n"
                "1. 将各场景配音按时间线对齐到对应视频片段位置\n"
                "2. 背景音乐铺底，贯穿全片\n"
                "3. 有对话时自动降低背景音乐音量 (ducking)\n"
                "   - 对话段: 背景音乐降至 20% 音量\n"
                "   - 无对话段: 背景音乐 60-80% 音量\n"
                "4. 开头前 2 秒背景音乐从 0 淡入\n"
                "5. 结尾最后 3 秒全部音频淡出\n"
                "6. 确保音频总时长与视频完全匹配\n\n"
                "技术要求：\n"
                "- 采样率: 44100Hz\n"
                "- 声道: 立体声\n"
                "- 格式: AAC\n"
                "- LUFS 响度目标: -14 LUFS (适合网络播放)\n\n"
                "输出路径: {output_dir}/temp/mixed_audio.aac"
            ),
            expected_output="混音后的音频文件路径和响度信息",
            agent=self._audio_mixer(),
        )

    def _subtitle_task(self) -> Task:
        """烧入字幕"""
        screenplay = self.project_state.screenplay
        has_dialogue = any(
            s.dialogue for s in (screenplay.scenes if screenplay else [])
        )

        return Task(
            description=(
                "为影片添加字幕：\n\n"
                f"{'有对话内容需要字幕' if has_dialogue else '仅添加标题字幕'}\n\n"
                "字幕规则：\n"
                "1. 对话字幕居中显示在画面下方 1/6 处\n"
                "2. 字体选择: 无衬线字体 (Noto Sans CJK for 中文)\n"
                "3. 字号: 适中（不遮挡画面）\n"
                "4. 样式: 白色文字 + 黑色描边(2px) 确保可读性\n"
                "5. 时间轴: 与配音精确同步\n"
                "6. 开头可添加片名 (居中、大号字体，持续 3 秒)\n"
                "7. 结尾可添加制作信息\n\n"
                "先生成 SRT 字幕文件，然后烧入视频。\n"
                "输出路径: {output_dir}/temp/subtitled.mp4"
            ),
            expected_output="带字幕的视频文件路径",
            agent=self._video_editor(),
        )

    def _color_grading_task(self) -> Task:
        """全片调色 — 结合风格基底 + 情绪曲线逐场景微调"""
        color_params = self.style_config.color_grading_params

        # 构建情绪曲线的逐场景调色参数
        emotion_color_note = ""
        curve_data = self.project_state.emotion_curve_data
        if curve_data:
            curve = EmotionCurve()
            for d in curve_data:
                curve.add_point(EmotionPoint(
                    scene_id=d["scene_id"],
                    tension=d["tension"],
                    valence=d["valence"],
                    energy=d["energy"],
                    mood_label=d.get("mood_label", ""),
                ))
            mapper = EmotionToParamsMapper()
            color_lines = []
            for point in curve.points:
                params = mapper.map_scene(point)
                cg = params.color_grading
                color_lines.append(
                    f"  Scene {point.scene_id} ({point.mood_label or 'N/A'}): "
                    f"sat={cg.saturation_offset:+.3f}, "
                    f"contrast={cg.contrast_offset:+.3f}, "
                    f"temp={cg.temperature_offset:+.3f}, "
                    f"brightness={cg.brightness_offset:+.3f}, "
                    f"vignette={cg.vignette_strength:.2f}"
                )
            emotion_color_note = (
                "\n[Emotion Curve → Per-Scene Color Grading Offsets]\n"
                "These offsets should be APPLIED ON TOP of the global style "
                "color grading below. They create emotional variation while "
                "maintaining overall style unity:\n"
                + "\n".join(color_lines)
                + "\n\n"
                "Implementation: Apply global style LUT first, then per-scene "
                "adjustments using FFmpeg eq/colorbalance filters with "
                "time-segmented filter graphs.\n\n"
            )

        return Task(
            description=(
                f"对全片进行 {self.style_config.display_name} 风格的调色：\n\n"
                f"【全局风格调色参数 (Base)】\n"
                f"- 对比度: {color_params.get('contrast', 1.0)}\n"
                f"- 饱和度: {color_params.get('saturation', 1.0)}\n"
                f"- 色温偏移: {color_params.get('temperature', 'neutral')}\n"
                f"- 暗部色调: {color_params.get('shadows_tint', 'neutral')}\n"
                f"- 高光色调: {color_params.get('highlights_tint', 'neutral')}\n"
                f"- 暗角强度: {color_params.get('vignette', 0)}\n\n"
                f"{emotion_color_note}"
                "调色原则：\n"
                "1. 确保全片色调统一（不同场景由于 AI 生成可能有色差）\n"
                "2. 先做全局校正（白平衡、曝光），再做风格化\n"
                "3. 在风格基底上叠加情绪曲线的逐场景微调\n"
                "4. 保持肤色自然（如有人物的话）\n"
                "5. 暗部不能死黑，高光不能过曝\n"
                "6. 情绪变化过渡要平滑，不要在场景边界突变\n\n"
                "使用 FFmpeg colorbalance/curves/eq 滤镜组合完成。\n"
                "输出路径: {output_dir}/temp/color_graded.mp4"
            ),
            expected_output="调色后的视频文件路径",
            agent=self._colorist(),
        )

    def _final_export_task(self) -> Task:
        """最终导出"""
        return Task(
            description=(
                "将所有处理后的视频和音频合并为最终成片：\n\n"
                "导出流程：\n"
                "1. 将调色后的视频与混音后的音频合并\n"
                "2. 验证音视频同步\n"
                "3. 压缩编码为最终格式\n\n"
                "编码参数：\n"
                "- 容器: MP4\n"
                "- 视频编码: H.264 (libx264)\n"
                "- 视频码率: 8-12 Mbps (根据分辨率)\n"
                "- 音频编码: AAC\n"
                "- 音频码率: 192 kbps\n"
                "- 帧率: 24fps (电影标准)\n"
                "- 关键帧间隔: 48 帧\n"
                "- Profile: High\n"
                "- Pixel format: yuv420p (兼容性最佳)\n\n"
                "最终检查：\n"
                "- 确认视频可以正常播放\n"
                "- 确认没有音画不同步\n"
                "- 确认文件大小合理\n"
                "- 确认开头和结尾没有黑帧\n\n"
                "输出路径: {output_dir}/final_film.mp4"
            ),
            expected_output="最终成片文件路径、文件大小和总时长",
            agent=self._video_editor(),
        )