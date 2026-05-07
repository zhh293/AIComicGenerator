"""素材生成 Crew — 生成视频片段、图片、配音和音乐"""

from __future__ import annotations

from crewai import Agent, Crew, Process, Task

from src.config import settings
from src.consistency.character_manager import CharacterConsistencyManager
from src.consistency.scene_continuity import SceneContinuityManager
from src.consistency.style_anchor import StyleAnchor
from src.emotion.curve import EmotionCurve, EmotionPoint, EmotionQuantizer
from src.emotion.mapper import EmotionToParamsMapper, SceneProductionParams
from src.flow.state import FilmProjectState, SceneAssetBundle
from src.llm import get_llm
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

        # 情绪曲线 → 制作参数映射
        self._emotion_mapper = EmotionToParamsMapper()
        self._scene_params: dict[int, SceneProductionParams] = {}
        self._build_scene_emotion_params()

        # API 适配器
        self.api_adapter = APIPromptAdapter(style_config)

        # 工具实例化
        self._video_tool = VideoGenerationTool()
        self._image_tool = ImageGenerationTool()
        self._tts_tool = TTSSynthesisTool()
        self._music_tool = MusicGenerationTool() if settings.enable_music_generation else None
        self._probe_tool = FFmpegProbeTool()
        self._frame_tool = FFmpegFrameExtractTool()

    def _build_scene_emotion_params(self) -> None:
        """从 state 中的 emotion_curve_data 构建每场景制作参数"""
        curve_data = self.project_state.emotion_curve_data
        if not curve_data:
            # 如果没有预计算的情绪曲线，当场从 screenplay 场景计算
            screenplay = self.project_state.screenplay
            if screenplay and screenplay.scenes:
                quantizer = EmotionQuantizer()
                curve = quantizer.build_curve_from_scenes(screenplay.scenes)
                params_list = self._emotion_mapper.map_curve(curve)
                for p in params_list:
                    self._scene_params[p.scene_id] = p
            return

        # 从序列化数据重建
        curve = EmotionCurve()
        for d in curve_data:
            point = EmotionPoint(
                scene_id=d["scene_id"],
                tension=d["tension"],
                valence=d["valence"],
                energy=d["energy"],
                mood_label=d.get("mood_label", ""),
            )
            curve.add_point(point)

        params_list = self._emotion_mapper.map_curve(curve)
        for p in params_list:
            self._scene_params[p.scene_id] = p

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

        # Phase 1: 生成角色参考图
        tasks.append(self._generate_character_refs_task())

        # Phase 2: 锁定参考图 — 一致性检查员验证并选择最佳参考图
        tasks.append(self._lock_reference_images_task())

        # Phase 3: 为每个场景生成素材（此时参考图已锁定）
        for scene in screenplay.scenes:
            tasks.append(self._generate_scene_visual_task(scene.scene_id))
            if scene.dialogue or scene.narration:
                tasks.append(self._generate_scene_audio_task(scene.scene_id))

        # Phase 4: 生成全片背景音乐（仅在启用时）
        if settings.enable_music_generation:
            tasks.append(self._generate_background_music_task())

        # Phase 5: 最终一致性检查
        tasks.append(self._consistency_check_task())

        return tasks

    def _generate_character_refs_task(self) -> Task:
        """生成角色参考图并锁定为全片身份约束"""
        screenplay = self.project_state.screenplay
        characters_desc = "\n".join(
            f"- {c.name}: {c.appearance.age}岁{c.appearance.gender}, "
            f"{c.appearance.hair_style} {c.appearance.hair_color}发, "
            f"{c.appearance.eye_color}瞳, {c.appearance.height_cm}cm, "
            f"{c.appearance.build}体型, 穿着{c.outfit.main_clothing}"
            for c in (screenplay.characters if screenplay else [])
        )

        return Task(
            description=(
                "Generate reference images for the following characters. These "
                "images will be LOCKED as identity anchors — all subsequent scenes "
                "MUST use them as image_reference to guarantee appearance consistency.\n\n"
                f"Characters:\n{characters_desc}\n\n"
                "Requirements:\n"
                "1. Generate 1 front-facing half-body reference per character\n"
                "2. Clean/minimal background to isolate character features\n"
                "3. Use EXACT appearance details from character profiles (skin tone hex, "
                "   hair style, eye color, distinctive features)\n"
                f"4. Style prefix: {self.style_config.visual_prefix[:80]}...\n"
                "5. Resolution: at least 1024x1024\n"
                "6. Neutral expression, good lighting, sharp focus\n\n"
                "CRITICAL: These reference images are the 'identity cards' for each "
                "character. Record each image path — they will be passed as "
                "reference_image parameter to ALL subsequent video generation calls "
                "for scenes containing that character. If a character does not look "
                "identical to their reference image in the generated video, the "
                "consistency check WILL fail.\n\n"
                "Output: {character_name: image_path} mapping for every character."
            ),
            expected_output=(
                "JSON mapping of character names to their locked reference image paths"
            ),
            agent=self._visual_director(),
        )

    def _lock_reference_images_task(self) -> Task:
        """锁定最佳角色参考图 — 作为后续全部场景的身份硬约束"""
        screenplay = self.project_state.screenplay
        character_names = [c.name for c in (screenplay.characters if screenplay else [])]

        return Task(
            description=(
                "Review and LOCK the character reference images generated in the "
                "previous task. This is a critical quality gate.\n\n"
                f"Characters to verify: {', '.join(character_names)}\n\n"
                "Verification steps for each reference image:\n"
                "1. Extract the image frame using FFmpeg probe/frame tools\n"
                "2. Check that the character matches their profile description:\n"
                "   - Face clearly visible and in focus\n"
                "   - Correct hair style and color\n"
                "   - Correct skin tone and build\n"
                "   - Clothing matches character outfit description\n"
                "   - No background clutter or artifacts\n"
                "3. If an image does NOT match the character profile, flag it for "
                "   regeneration with specific corrections\n"
                "4. Once verified, output the FINAL mapping of character names to "
                "   their locked reference image paths\n\n"
                "IMPORTANT: The locked images become immutable identity constraints. "
                "All subsequent scene generation will use these exact images as "
                "`reference_image` parameters. Choose carefully — the ENTIRE film's "
                "visual coherence depends on this step.\n\n"
                "Output format (JSON):\n"
                "{\n"
                '  "locked_references": {\n'
                '    "character_name": "/path/to/verified_reference.png",\n'
                "    ...\n"
                "  },\n"
                '  "issues": []\n'
                "}"
            ),
            expected_output=(
                "JSON object with locked_references mapping (character_name → image_path) "
                "and any issues found during verification"
            ),
            agent=self._consistency_checker(),
        )

    def _generate_scene_visual_task(self, scene_id: str) -> Task:
        """生成单个场景的视频片段 — 强制使用角色参考图"""
        screenplay = self.project_state.screenplay
        scene = next(
            (s for s in (screenplay.scenes if screenplay else []) if s.scene_id == scene_id),
            None,
        )
        if not scene:
            raise ValueError(f"Scene {scene_id} not found in screenplay")

        # 获取该场景中涉及的角色参考图路径
        ref_images = self.project_state.character_reference_images or {}
        scene_characters = [
            ca.character_name for ca in scene.characters_in_scene
        ]
        ref_image_instructions = ""
        if scene_characters and ref_images:
            ref_lines = []
            for char_name in scene_characters:
                img_path = ref_images.get(char_name)
                if img_path:
                    ref_lines.append(f"  - {char_name}: {img_path}")
            if ref_lines:
                ref_image_instructions = (
                    "\n[LOCKED Character Reference Images — MANDATORY]\n"
                    "You MUST pass these as `reference_image` / `image_reference` "
                    "parameter to the video generation API. Do NOT generate without them:\n"
                    + "\n".join(ref_lines)
                    + "\n\n"
                    "If the API supports image-to-video mode, use the reference image "
                    "as the starting frame/identity anchor. The generated character "
                    "MUST match the reference image in facial features, hair, skin tone, "
                    "and clothing.\n\n"
                )

        # 获取上一场景末帧用于时间连续性
        prev_scene_id = scene_id - 1 if isinstance(scene_id, int) else None
        continuity_note = ""
        if prev_scene_id and prev_scene_id in (self.project_state.scene_last_frames or {}):
            last_frame = self.project_state.scene_last_frames[prev_scene_id]
            continuity_note = (
                f"\n[Temporal Continuity]\n"
                f"Previous scene's last frame: {last_frame}\n"
                f"Use this as visual context to ensure smooth transition.\n\n"
            )

        # 情绪曲线驱动的镜头和调色参数
        emotion_instructions = ""
        scene_params = self._scene_params.get(scene_id)
        if scene_params:
            cam = scene_params.camera
            color = scene_params.color_grading
            em = scene_params.emotion
            emotion_instructions = (
                f"\n[Emotion-Driven Parameters — Scene Tension: {em.tension:.2f}, "
                f"Valence: {em.valence:.2f}, Energy: {em.energy:.2f}]\n"
                f"Camera guidance from emotion curve:\n"
                f"  - Preferred shots: {', '.join(cam.preferred_shot_types)}\n"
                f"  - Camera speed: {cam.camera_speed:.2f} (0=static, 1=fast)\n"
                f"  - Handheld intensity: {cam.handheld_intensity:.2f}\n"
                f"  - Depth of field: {cam.depth_of_field}\n"
                f"Color grading targets:\n"
                f"  - Saturation offset: {color.saturation_offset:+.3f}\n"
                f"  - Contrast offset: {color.contrast_offset:+.3f}\n"
                f"  - Color temperature: {color.temperature_offset:+.3f} "
                f"({'warm' if color.temperature_offset > 0 else 'cool'})\n"
                f"  - Vignette: {color.vignette_strength:.2f}\n\n"
                "Apply these parameters to prompt engineering and post-processing.\n\n"
            )

        return Task(
            description=(
                f"Generate video clip for scene {scene_id}:\n\n"
                f"[Environment]\n{scene.environment_description}\n\n"
                f"[Visual Prompt]\n{scene.visual_prompt}\n\n"
                f"[Camera]\n"
                f"- Shot type: {scene.shot_type}\n"
                f"- Movement: {scene.camera_movement}\n"
                f"- Duration: {scene.duration_seconds} seconds\n\n"
                f"{ref_image_instructions}"
                f"{continuity_note}"
                f"{emotion_instructions}"
                "Generation workflow:\n"
                "1. ALWAYS use image-to-video mode when reference images are available\n"
                "2. Pass reference_image as the identity anchor for the character\n"
                "3. Combine visual_prompt + character appearance for the text prompt\n"
                "4. Apply emotion-driven camera and color grading parameters\n"
                "5. Record generated video file path and actual duration\n"
                "6. Extract LAST FRAME and save path for next scene continuity\n\n"
                f"Preferred API provider: {settings.video_api_provider}\n"
                "Ensure resolution and frame rate meet composition requirements.\n"
                "IMPORTANT: If a character reference image exists, image-to-video "
                "mode is NOT optional — it is REQUIRED."
            ),
            expected_output=(
                f"Video file path, metadata (duration, resolution), and "
                f"last_frame_path for scene {scene_id}"
            ),
            agent=self._visual_director(),
        )

    def _generate_scene_audio_task(self, scene_id: str) -> Task:
        """生成单个场景的配音 — 使用情绪曲线驱动语音参数"""
        screenplay = self.project_state.screenplay
        scene = next(
            (s for s in (screenplay.scenes if screenplay else []) if s.scene_id == scene_id),
            None,
        )
        if not scene:
            raise ValueError(f"Scene {scene_id} not found in screenplay")

        text_content = scene.dialogue or scene.narration or ""

        # 情绪驱动的配音参数
        voice_emotion_note = ""
        scene_params = self._scene_params.get(scene_id)
        if scene_params:
            vp = scene_params.voice
            em = scene_params.emotion
            voice_emotion_note = (
                f"\n[Emotion-Driven Voice Parameters]\n"
                f"Scene emotion: tension={em.tension:.2f}, "
                f"valence={em.valence:.2f}, energy={em.energy:.2f}\n"
                f"  - Speed multiplier: {vp.speed_multiplier}x\n"
                f"  - Volume gain: {vp.volume_gain_db:+.1f} dB\n"
                f"  - Emotion tag: {vp.emotion_tag}\n"
                f"  - Pitch shift: {vp.pitch_shift:+.1f} semitones\n"
                f"  - Pause weight: {vp.pause_weight} "
                f"({'more pauses' if vp.pause_weight > 1.0 else 'fewer pauses'})\n\n"
                "Apply these parameters when calling the TTS tool. "
                "The speed and emotion settings are derived from the global "
                "emotion curve to maintain emotional coherence across the film.\n\n"
            )

        return Task(
            description=(
                f"Generate voiceover for scene {scene_id}:\n\n"
                f"[Content]\n{text_content}\n\n"
                f"[Mood]\n{scene.mood}\n\n"
                f"{voice_emotion_note}"
                "Requirements:\n"
                "1. Select appropriate voice_id based on speaking character\n"
                "2. Apply emotion-driven speed and volume parameters above\n"
                "3. Voiceover duration must not exceed video clip duration\n"
                "4. For narration, use a warm neutral voice with emotion tag\n"
                "5. Output WAV or MP3 format\n"
                "6. Record file path and exact duration"
            ),
            expected_output=f"Voiceover file path and duration for scene {scene_id}",
            agent=self._audio_producer(),
        )

    def _generate_background_music_task(self) -> Task:
        """生成全片背景音乐 — 使用情绪曲线驱动音乐参数"""
        screenplay = self.project_state.screenplay
        total_duration = sum(
            s.duration_seconds for s in (screenplay.scenes if screenplay else [])
        )

        # 构建全片情绪音乐参数摘要
        music_curve_note = ""
        if self._scene_params:
            segments = []
            for scene_id in sorted(self._scene_params.keys()):
                sp = self._scene_params[scene_id]
                mp = sp.music
                segments.append(
                    f"  Scene {scene_id}: BPM {mp.bpm_range[0]}-{mp.bpm_range[1]}, "
                    f"{mp.mode} mode, density={mp.density:.2f}, "
                    f"dynamics={mp.dynamics}, instruments=[{mp.instruments_hint}]"
                )
            music_curve_note = (
                "\n[Emotion Curve → Music Parameters (per scene)]\n"
                + "\n".join(segments)
                + "\n\n"
                "The music should FOLLOW this emotional progression. "
                "Transition smoothly between scenes — do not abruptly "
                "change BPM or dynamics. Use the parameters as targets "
                "that the music gradually approaches.\n\n"
            )

        return Task(
            description=(
                "Generate background music for the entire short film:\n\n"
                f"[Style] {self.style_config.display_name}\n"
                f"[Total Duration Required] {total_duration} seconds\n"
                f"[Emotional Arc] Starting from {screenplay.tone if screenplay else 'unknown'} "
                "tone, with dynamics matching the story progression\n\n"
                f"{music_curve_note}"
                "Generation strategy:\n"
                "1. Generate one complete background track (possibly in segments)\n"
                "2. Climax sections need more intense music (see emotion curve above)\n"
                "3. Include fade-in at opening and fade-out at ending\n"
                "4. Music must be instrumental only (no vocals)\n"
                "5. If total duration exceeds single-generation limit, generate in "
                "   segments aligned with emotion curve transitions\n"
                "6. Output WAV or MP3 format\n"
                "7. Match the mode (major/minor) and BPM targets from emotion curve"
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
