"""素材生成 Crew — 生成视频片段、图片、配音和音乐"""

from __future__ import annotations

from crewai import Agent, Crew, Process, Task

from src.config import settings
from src.consistency.character_manager import CharacterConsistencyManager
from src.llm import get_llm
from src.consistency.scene_continuity import SceneContinuityManager
from src.consistency.style_anchor import StyleAnchor
from src.flow.state import FilmProjectState, SceneAssetBundle
from src.style.api_adapter import APIPromptAdapter
from src.style.presets import StylePresetConfig
from src.tools.ffmpeg_tools import FFmpegFrameExtractTool, FFmpegProbeTool
from src.tools.image_gen_tool import ImageGenerationTool
from src.tools.music_gen_tool import MusicGenerationTool
from src.tools.tts_tool import TTSSynthesisTool
from src.tools.video_gen_tool import VideoGenerationTool


class AssetGenerationCrew:
    """
    素材生成 Crew

    包含三个 Agent：
    1. 视觉导演 - 负责调用图片/视频生成 API 生成视觉素材
    2. 音频制作人 - 负责 TTS 配音和背景音乐生成
    3. 一致性检查员 - 验证素材的角色/风格一致性

    核心机制：
    - 通过 CharacterConsistencyManager 保证角色一致性
    - 通过 StyleAnchor 锁定风格锚点
    - 通过 SceneContinuityManager 保证场景连续性
    """

    def __init__(
        self,
        style_config: StylePresetConfig,
        project_state: FilmProjectState,
    ):
        self.style_config = style_config
        self.project_state = project_state
        self._llm = get_llm()

        # 一致性管理器
        self.character_manager = CharacterConsistencyManager(settings.output_dir)
        self.style_anchor = StyleAnchor(style_config)
        self.scene_continuity = SceneContinuityManager(settings.output_dir)

        # API 适配器
        self.api_adapter = APIPromptAdapter(style_config)

        # 工具实例化
        self._video_tool = VideoGenerationTool()
        self._image_tool = ImageGenerationTool()
        self._tts_tool = TTSSynthesisTool()
        self._music_tool = MusicGenerationTool() if settings.enable_music_generation else None
        self._probe_tool = FFmpegProbeTool()
        self._frame_tool = FFmpegFrameExtractTool()

    def crew(self) -> Crew:
        """组装并返回 Crew 实例"""
        return Crew(
            agents=[
                self._visual_director(),
                self._audio_producer(),
                self._consistency_checker(),
            ],
            tasks=self._build_tasks(),
            process=Process.sequential,
            verbose=True,
        )

    # ================================================================
    # Agent 定义
    # ================================================================

    def _visual_director(self) -> Agent:
        return Agent(
            role="Visual Director",
            goal=(
                "Generate high-quality video clips and keyframe images based on "
                "screenplay scene visual prompts. Ensure visual style consistency "
                "and character appearance coherence across all scenes."
            ),
            backstory=(
                "You are an AI visual director combining artistic sensibility with "
                "technical expertise in generative AI models. You excel at prompt "
                "engineering for video/image generation APIs, knowing exactly how "
                "to phrase descriptions for optimal output quality. Your core skill "
                "is translating screenplay descriptions into precise API parameters "
                "while maintaining full-film visual consistency."
            ),
            tools=[
                self._video_tool,
                self._image_tool,
                self._probe_tool,
                self._frame_tool,
            ],
            llm=self._llm,
            verbose=True,
        )

    def _audio_producer(self) -> Agent:
        # 音频工具列表：TTS 必选，音乐生成可选
        audio_tools = [self._tts_tool]
        if self._music_tool:
            audio_tools.append(self._music_tool)

        goal_text = (
            "Generate high-quality voiceover for each scene's dialogue. "
            "Voiceover should match character personality and scene mood."
        )
        if self._music_tool:
            goal_text += (
                " Also produce fitting background music that complements "
                "the emotional arc of the story."
            )

        return Agent(
            role="Audio Producer",
            goal=goal_text,
            backstory=(
                "You are a seasoned film audio producer with extensive experience "
                "in voice direction. You understand the power of sound in short "
                "films - the right voice brings characters alive. You are proficient "
                "with TTS engine parameters (voice, emotion, speed)."
            ),
            tools=audio_tools,
            llm=self._llm,
            verbose=True,
        )

    def _consistency_checker(self) -> Agent:
        return Agent(
            role="Consistency Checker",
            goal=(
                "Verify character consistency, style consistency, and scene "
                "continuity across all generated assets. When inconsistencies "
                "are detected, provide specific correction suggestions."
            ),
            backstory=(
                "You are an extremely meticulous visual continuity supervisor. "
                "In the film industry, continuity errors are the most easily "
                "spotted by audiences - character hair color changes, sudden "
                "lighting shifts, object position jumps. Your job is to review "
                "frame by frame, ensuring every frame is perfectly consistent. "
                "You have an almost obsessive attention to detail."
            ),
            tools=[
                self._probe_tool,
                self._frame_tool,
            ],
            llm=self._llm,
            verbose=True,
        )

    # ================================================================
    # Task 构建
    # ================================================================

    def _build_tasks(self) -> list[Task]:
        """根据当前项目状态动态构建任务列表"""
        tasks: list[Task] = []

        screenplay = self.project_state.screenplay
        if not screenplay:
            raise ValueError("Screenplay must be available before asset generation")

        # 先生成角色参考图
        tasks.append(self._generate_character_refs_task())

        # 为每个场景生成素材
        for scene in screenplay.scenes:
            tasks.append(self._generate_scene_visual_task(scene.scene_id))
            if scene.dialogue or scene.narration:
                tasks.append(self._generate_scene_audio_task(scene.scene_id))

        # 生成全片背景音乐（仅在启用时）
        if settings.enable_music_generation:
            tasks.append(self._generate_background_music_task())

        # 最终一致性检查
        tasks.append(self._consistency_check_task())

        return tasks

    def _generate_character_refs_task(self) -> Task:
        """生成角色参考图"""
        screenplay = self.project_state.screenplay
        characters_desc = "\n".join(
            f"- {c.name}: {c.appearance.base_prompt}"
            for c in (screenplay.characters if screenplay else [])
        )

        return Task(
            description=(
                "Generate reference images for the following characters. These "
                "images will serve as anchors for all subsequent scene generation:\n\n"
                f"{characters_desc}\n\n"
                "Requirements:\n"
                "1. Generate 1 front-facing half-body reference image per character\n"
                "2. Use precise appearance descriptions from character profiles\n"
                f"3. Style prefix: {self.style_config.visual_prefix[:80]}...\n"
                "4. Use a plain or minimal background to highlight the character\n"
                "5. Ensure resolution is at least 1024x1024\n\n"
                "Record each image path for subsequent scene reference."
            ),
            expected_output="List of reference image paths for each character",
            agent=self._visual_director(),
        )

    def _generate_scene_visual_task(self, scene_id: str) -> Task:
        """生成单个场景的视频片段"""
        screenplay = self.project_state.screenplay
        scene = next(
            (s for s in (screenplay.scenes if screenplay else []) if s.scene_id == scene_id),
            None,
        )
        if not scene:
            raise ValueError(f"Scene {scene_id} not found in screenplay")

        return Task(
            description=(
                f"Generate video clip for scene {scene_id}:\n\n"
                f"[Environment]\n{scene.environment_description}\n\n"
                f"[Visual Prompt]\n{scene.visual_prompt}\n\n"
                f"[Camera]\n"
                f"- Shot type: {scene.shot_type}\n"
                f"- Movement: {scene.camera_movement}\n"
                f"- Duration: {scene.duration_seconds} seconds\n\n"
                "Generation workflow:\n"
                "1. Use visual_prompt + character reference images to call video API\n"
                "2. If character reference images available, use image-to-video mode\n"
                "3. Otherwise, use text-to-video mode\n"
                "4. Record generated video file path and actual duration\n"
                "5. Extract last frame as continuity reference for next scene\n\n"
                f"Preferred API provider: {settings.video_api_provider}\n"
                "Ensure resolution and frame rate meet composition requirements."
            ),
            expected_output=f"Video file path and metadata for scene {scene_id}",
            agent=self._visual_director(),
        )

    def _generate_scene_audio_task(self, scene_id: str) -> Task:
        """生成单个场景的配音"""
        screenplay = self.project_state.screenplay
        scene = next(
            (s for s in (screenplay.scenes if screenplay else []) if s.scene_id == scene_id),
            None,
        )
        if not scene:
            raise ValueError(f"Scene {scene_id} not found in screenplay")

        text_content = scene.dialogue or scene.narration or ""

        return Task(
            description=(
                f"Generate voiceover for scene {scene_id}:\n\n"
                f"[Content]\n{text_content}\n\n"
                f"[Mood]\n{scene.mood}\n\n"
                "Requirements:\n"
                "1. Select appropriate voice_id based on speaking character\n"
                "2. Adjust speed and emotion parameters to match scene mood\n"
                "3. Voiceover duration must not exceed video clip duration\n"
                "4. For narration, use a warm neutral voice\n"
                "5. Output WAV or MP3 format\n"
                "6. Record file path and exact duration"
            ),
            expected_output=f"Voiceover file path and duration for scene {scene_id}",
            agent=self._audio_producer(),
        )

    def _generate_background_music_task(self) -> Task:
        """生成全片背景音乐"""
        screenplay = self.project_state.screenplay
        total_duration = sum(
            s.duration_seconds for s in (screenplay.scenes if screenplay else [])
        )

        return Task(
            description=(
                "Generate background music for the entire short film:\n\n"
                f"[Style] {self.style_config.display_name}\n"
                f"[Total Duration Required] {total_duration} seconds\n"
                f"[Emotional Arc] Starting from {screenplay.tone if screenplay else 'unknown'} "
                "tone, with dynamics matching the story progression\n\n"
                "Generation strategy:\n"
                "1. Generate one complete background track (possibly in segments)\n"
                "2. Climax sections need more intense music\n"
                "3. Include fade-in at opening and fade-out at ending\n"
                "4. Music must be instrumental only (no vocals)\n"
                "5. If total duration exceeds single-generation limit, generate in "
                "   segments and mark splice points\n"
                "6. Output WAV or MP3 format"
            ),
            expected_output=(
                "Background music file path, duration, and splicing plan if segmented"
            ),
            agent=self._audio_producer(),
        )

    def _consistency_check_task(self) -> Task:
        """全面一致性检查"""
        return Task(
            description=(
                "Perform comprehensive consistency check on all generated assets:\n\n"
                "[Character Consistency]\n"
                "- Extract keyframes from each video\n"
                "- Compare against character reference images\n"
                "- Focus on hair color, skin tone, clothing identification\n\n"
                "[Style Consistency]\n"
                "- Verify all scenes maintain unified visual style\n"
                "- Compare against first scene (style anchor)\n"
                "- Focus on color palette, lighting style, texture quality\n\n"
                "[Scene Continuity]\n"
                "- Check for jarring jumps between adjacent scenes\n"
                "- Verify same environment consistency across different shots\n"
                "- Check lighting changes are logical\n\n"
                "Output: Generate correction suggestions for each issue, "
                "rated by severity (1-5 scale)."
            ),
            expected_output=(
                "Consistency check report: issue list with severity ratings, "
                "descriptions, and correction suggestions"
            ),
            agent=self._consistency_checker(),
        )
