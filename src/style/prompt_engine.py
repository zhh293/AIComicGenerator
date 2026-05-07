"""Prompt 模板引擎 — 将风格配置+场景信息+角色信息组装为最终生成指令"""

from __future__ import annotations

from typing import List, Optional

from src.flow.state import Character, Scene, SceneCharacterAction
from src.style.presets import StylePresetConfig


class PromptTemplateEngine:
    """
    Prompt 模板引擎
    
    职责：
    1. 将风格前缀、场景描述、角色描述、光照和镜头信息组装为完整的视觉 Prompt
    2. 为不同 API 格式化 negative prompt
    3. 生成音乐和 TTS 的 Prompt
    """

    def __init__(self, style_config: StylePresetConfig):
        self.style = style_config

    def render_scene_visual_prompt(
        self,
        scene: Scene,
        characters: List[Character],
        include_style_prefix: bool = True,
    ) -> str:
        """
        渲染完整的场景视觉生成 Prompt
        
        组装顺序：风格前缀 → 环境描述 → 角色描述 → 光照 → 镜头 → 氛围
        """
        parts: List[str] = []

        # 1. 风格前缀
        if include_style_prefix:
            parts.append(self.style.visual_prefix)

        # 2. 场景环境
        env_desc = self._build_environment_block(scene)
        parts.append(env_desc)

        # 3. 角色描述（精确到外貌细节）
        char_block = self._build_character_block(scene.characters_in_scene, characters)
        if char_block:
            parts.append(char_block)

        # 4. 光照
        lighting_block = self._build_lighting_block(scene)
        parts.append(lighting_block)

        # 5. 镜头与构图
        camera_block = self._build_camera_block(scene)
        parts.append(camera_block)

        # 6. 情绪氛围
        if scene.mood and scene.mood != "neutral":
            parts.append(f"{scene.mood} atmosphere and mood")

        return ", ".join(filter(None, parts))

    def render_negative_prompt(self, extra_negatives: Optional[List[str]] = None) -> str:
        """渲染 negative prompt"""
        base = self.style.negative_prompt
        if extra_negatives:
            extras = ", ".join(extra_negatives)
            return f"{base}, {extras}"
        return base

    def render_music_prompt(
        self,
        mood: str = "neutral",
        tempo: str = "medium",
        duration_seconds: float = 60.0,
        scene_description: str = "",
    ) -> str:
        """渲染音乐生成 Prompt"""
        parts = [
            self.style.audio.music_style,
            f"{mood} emotional tone",
            f"{tempo} tempo",
        ]

        if self.style.audio.music_instruments:
            parts.append(f"featuring {self.style.audio.music_instruments}")

        if scene_description:
            parts.append(f"accompanying a scene of: {scene_description}")

        parts.append(f"duration approximately {duration_seconds:.0f} seconds")
        parts.append("seamless loop friendly, gentle fade out ending")

        return ", ".join(parts)

    def render_tts_direction(self, character: Optional[Character] = None) -> str:
        """渲染 TTS 方向指示（用于指导语音合成的情感和风格）"""
        base_style = self.style.audio.voice_style

        if character and character.voice_description:
            return f"{base_style}. Character voice: {character.voice_description}"

        return base_style

    def get_generation_params(self) -> dict:
        """获取生成 API 参数字典"""
        return {
            "cfg_scale": self.style.cfg_scale,
            "consistency_weight": self.style.consistency_weight,
            "motion_intensity": self.style.motion_intensity,
            "preferred_api": self.style.preferred_api,
            "aspect_ratio": self.style.camera.preferred_aspect_ratio,
        }

    def get_transition_config(self, scene: Scene) -> dict:
        """获取转场配置"""
        transition = scene.transition_to_next.value
        # 如果场景指定的转场不在风格偏好中，使用风格默认的第一个
        if (
            self.style.preferred_transitions
            and transition not in self.style.preferred_transitions
        ):
            transition = self.style.preferred_transitions[0]

        return {
            "transition_type": transition,
            "duration": scene.transition_duration or self.style.default_transition_duration,
        }

    # ================================================================
    # 私有方法 — 构建各个 Prompt 子块
    # ================================================================

    def _build_environment_block(self, scene: Scene) -> str:
        """构建环境描述块"""
        parts = []

        if scene.location:
            parts.append(f"setting: {scene.location}")

        if scene.environment_description:
            parts.append(scene.environment_description)

        if scene.time_of_day:
            parts.append(f"time: {scene.time_of_day}")

        if scene.weather and scene.weather != "clear":
            parts.append(f"weather: {scene.weather}")

        return ", ".join(parts)

    def _build_character_block(
        self,
        scene_characters: List[SceneCharacterAction],
        all_characters: List[Character],
    ) -> str:
        """构建角色描述块 — 包含完整外貌以确保一致性"""
        if not scene_characters:
            return ""

        char_descriptions = []
        for sc in scene_characters:
            # 从角色注册表中查找完整信息
            character = next(
                (c for c in all_characters if c.name == sc.character_name), None
            )
            if character:
                desc = character.to_visual_prompt(
                    expression=sc.expression,
                    pose=sc.action,
                )
                if sc.position:
                    desc += f" Position in frame: {sc.position}."
                char_descriptions.append(desc)

        if char_descriptions:
            return "Characters: " + " | ".join(char_descriptions)
        return ""

    def _build_lighting_block(self, scene: Scene) -> str:
        """构建光照描述块"""
        # 优先使用场景指定的时间，否则使用风格默认
        time = scene.time_of_day or self.style.lighting.default_time_of_day

        return (
            f"lighting: {self.style.lighting.key_light}, "
            f"{self.style.lighting.ambient}, "
            f"time of day: {time}"
        )

    def _build_camera_block(self, scene: Scene) -> str:
        """构建镜头描述块"""
        parts = [f"shot type: {scene.shot_type.value}"]

        if scene.camera_movement.value != "static":
            parts.append(f"camera movement: {scene.camera_movement.value}")

        parts.append(f"lens: {self.style.camera.default_lens}")
        parts.append(f"depth of field: {self.style.camera.depth_of_field}")

        return ", ".join(parts)
