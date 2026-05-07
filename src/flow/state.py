"""FlowState 数据模型 — 定义整个生产流程中流转的所有数据结构"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


# ============================================================
# 枚举类型
# ============================================================


class StyleType(str, Enum):
    """风格类型枚举"""

    CINEMATIC = "cinematic"
    ANIME = "anime"
    CYBERPUNK = "cyberpunk"
    INK_WASH = "ink_wash"
    REALISTIC = "realistic"
    RETRO_FILM = "retro_film"


class TransitionType(str, Enum):
    """转场类型"""

    FADE = "fade"
    DISSOLVE = "dissolve"
    WIPE_LEFT = "wipeleft"
    WIPE_RIGHT = "wiperight"
    SLIDE_UP = "slideup"
    SLIDE_DOWN = "slidedown"
    PIXELIZE = "pixelize"
    CIRCLE_OPEN = "circleopen"
    CIRCLE_CLOSE = "circleclose"
    NONE = "none"


class CameraMovement(str, Enum):
    """镜头运动类型"""

    STATIC = "static"
    PAN_LEFT = "pan_left"
    PAN_RIGHT = "pan_right"
    TILT_UP = "tilt_up"
    TILT_DOWN = "tilt_down"
    DOLLY_IN = "dolly_in"
    DOLLY_OUT = "dolly_out"
    CRANE_UP = "crane_up"
    CRANE_DOWN = "crane_down"
    TRACKING = "tracking"
    HANDHELD = "handheld"
    AERIAL = "aerial"


class ShotType(str, Enum):
    """镜头景别"""

    EXTREME_WIDE = "extreme_wide"
    WIDE = "wide"
    MEDIUM = "medium"
    MEDIUM_CLOSE = "medium_close"
    CLOSE_UP = "close_up"
    EXTREME_CLOSE = "extreme_close"
    OVER_SHOULDER = "over_shoulder"
    POV = "pov"


# ============================================================
# 角色模型
# ============================================================


class CharacterAppearance(BaseModel):
    """角色外貌详细描述 — 用于保持视觉一致性"""

    age: int = Field(description="年龄")
    gender: str = Field(description="性别")
    ethnicity: str = Field(description="肤色/种族描述")
    skin_tone: str = Field(description="肤色色号，如 #F5DEB3")
    height_cm: int = Field(description="身高（厘米）")
    build: str = Field(description="体型，如 slender / athletic / stocky")
    hair_style: str = Field(description="发型")
    hair_color: str = Field(description="发色")
    eye_color: str = Field(description="瞳色")
    distinctive_features: List[str] = Field(
        default_factory=list, description="标志性特征，如痣、疤痕、纹身"
    )


class CharacterOutfit(BaseModel):
    """角色服装描述"""

    main_clothing: str = Field(description="主要服装描述")
    accessories: List[str] = Field(default_factory=list, description="配饰列表")
    shoes: str = Field(default="", description="鞋子描述")
    color_palette: List[str] = Field(default_factory=list, description="服装主色调")


class Character(BaseModel):
    """完整角色档案"""

    name: str = Field(description="角色名")
    appearance: CharacterAppearance = Field(description="外貌详细描述")
    outfit: CharacterOutfit = Field(description="服装描述")
    personality: str = Field(description="性格特征概述")
    voice_description: str = Field(default="", description="音色描述，用于 TTS 选择")
    voice_id: Optional[str] = Field(default=None, description="TTS 音色 ID")
    reference_image_url: Optional[str] = Field(default=None, description="角色参考图 URL")

    def to_visual_prompt(self, expression: str = "neutral", pose: str = "standing") -> str:
        """将角色信息转化为视觉生成 Prompt 片段"""
        a = self.appearance
        o = self.outfit

        features_str = ", ".join(a.distinctive_features) if a.distinctive_features else "none"
        accessories_str = ", ".join(o.accessories) if o.accessories else "none"

        return (
            f"{self.name}: {a.age}-year-old {a.gender}, {a.ethnicity} complexion "
            f"(skin tone {a.skin_tone}), {a.hair_style} {a.hair_color} hair, "
            f"{a.eye_color} eyes, {a.height_cm}cm tall, {a.build} build. "
            f"Wearing: {o.main_clothing}, accessories: {accessories_str}, "
            f"shoes: {o.shoes}. "
            f"Distinctive features: {features_str}. "
            f"Expression: {expression}. Pose: {pose}."
        )


# ============================================================
# 场景模型
# ============================================================


class SceneCharacterAction(BaseModel):
    """场景中角色的具体动作"""

    character_name: str = Field(description="角色名")
    action: str = Field(description="动作描述")
    expression: str = Field(default="neutral", description="表情")
    position: str = Field(default="center", description="画面位置")


class Scene(BaseModel):
    """单个场景完整定义"""

    scene_id: int = Field(description="场景编号（从1开始）")
    title: str = Field(default="", description="场景标题/简述")
    location: str = Field(description="场景地点")
    time_of_day: str = Field(default="day", description="时间段")
    weather: str = Field(default="clear", description="天气/氛围")
    environment_description: str = Field(description="环境详细描述")

    # 镜头
    shot_type: ShotType = Field(default=ShotType.MEDIUM, description="景别")
    camera_movement: CameraMovement = Field(default=CameraMovement.STATIC, description="镜头运动")

    # 角色与动作
    characters_in_scene: List[SceneCharacterAction] = Field(
        default_factory=list, description="场景中的角色及其动作"
    )

    # 内容
    visual_prompt: str = Field(default="", description="视觉生成 Prompt（英文）")
    dialogue: Optional[str] = Field(default=None, description="对话内容")
    narration: Optional[str] = Field(default=None, description="旁白内容")
    sound_effects: List[str] = Field(default_factory=list, description="音效描述")
    mood: str = Field(default="neutral", description="情绪基调")

    # 时间与转场
    duration_seconds: float = Field(default=5.0, description="场景时长（秒）")
    transition_to_next: TransitionType = Field(
        default=TransitionType.DISSOLVE, description="到下一场景的转场"
    )
    transition_duration: float = Field(default=0.5, description="转场时长（秒）")


# ============================================================
# 剧本模型
# ============================================================


class ActStructure(BaseModel):
    """幕结构"""

    act_number: int = Field(description="第几幕")
    title: str = Field(description="幕标题")
    description: str = Field(description="该幕概述")
    scene_ids: List[int] = Field(description="包含的场景编号列表")


class Screenplay(BaseModel):
    """完整剧本"""

    title: str = Field(description="作品标题")
    logline: str = Field(description="一句话概述")
    synopsis: str = Field(description="故事梗概")
    theme: str = Field(description="核心主题")
    tone: str = Field(description="整体基调")
    acts: List[ActStructure] = Field(description="幕结构")
    scenes: List[Scene] = Field(description="所有场景列表")
    characters: List[Character] = Field(description="角色列表")
    total_duration_seconds: float = Field(description="预计总时长（秒）")

    @property
    def character_names(self) -> List[str]:
        return [c.name for c in self.characters]

    def get_character(self, name: str) -> Optional[Character]:
        """根据名字获取角色"""
        for c in self.characters:
            if c.name == name:
                return c
        return None


# ============================================================
# 素材模型
# ============================================================


class GeneratedVideoAsset(BaseModel):
    """生成的视频素材"""

    scene_id: int
    video_path: str = Field(description="视频文件路径")
    duration_seconds: float = Field(description="实际时长")
    resolution: str = Field(default="1920x1080", description="分辨率")
    fps: int = Field(default=24, description="帧率")
    first_frame_path: Optional[str] = Field(default=None, description="首帧图片路径")
    last_frame_path: Optional[str] = Field(default=None, description="末帧图片路径")


class GeneratedAudioAsset(BaseModel):
    """生成的音频素材"""

    scene_id: int
    dialogue_path: Optional[str] = Field(default=None, description="对话/旁白音频路径")
    sfx_paths: List[str] = Field(default_factory=list, description="音效文件路径列表")
    duration_seconds: float = Field(default=0.0, description="音频时长")


class GeneratedMusicAsset(BaseModel):
    """生成的音乐素材"""

    music_path: str = Field(description="背景音乐文件路径")
    duration_seconds: float = Field(description="音乐时长")
    style_description: str = Field(default="", description="音乐风格描述")


class SceneAssetBundle(BaseModel):
    """单个场景的全部素材包"""

    scene_id: int
    video: Optional[GeneratedVideoAsset] = None
    audio: Optional[GeneratedAudioAsset] = None
    subtitle_text: Optional[str] = None


# ============================================================
# 质量评估模型
# ============================================================


class QualityScore(BaseModel):
    """质量评分"""

    dimension: str = Field(description="评估维度")
    score: float = Field(ge=0.0, le=1.0, description="分数 0-1")
    feedback: str = Field(default="", description="反馈说明")


class StageQualityReport(BaseModel):
    """某阶段的质量报告"""

    stage_name: str
    scores: List[QualityScore] = Field(default_factory=list)
    average_score: float = Field(default=0.0)
    passed: bool = Field(default=False)
    retry_count: int = Field(default=0)
    improvement_suggestions: List[str] = Field(default_factory=list)


# ============================================================
# Flow 全局状态
# ============================================================


class FilmProjectState(BaseModel):
    """Flow 全局状态 — 在整个生产流程中流转的核心数据"""

    # === 用户输入 ===
    user_prompt: str = Field(default="", description="用户原始描述")
    style: StyleType = Field(default=StyleType.CINEMATIC, description="风格选择")
    target_duration_seconds: float = Field(default=60.0, description="目标时长（秒）")

    # === 各阶段产出 ===
    screenplay: Optional[Screenplay] = Field(default=None, description="完整剧本")
    scene_assets: List[SceneAssetBundle] = Field(
        default_factory=list, description="各场景素材包"
    )
    music: Optional[GeneratedMusicAsset] = Field(default=None, description="背景音乐")
    final_video_path: Optional[str] = Field(default=None, description="最终视频路径")

    # === 一致性管理 ===
    character_registry: List[Character] = Field(
        default_factory=list, description="角色注册表"
    )
    character_reference_images: dict = Field(
        default_factory=dict, description="角色参考图 {角色名: 路径}"
    )
    style_anchor_frame: Optional[str] = Field(
        default=None, description="风格锚定帧路径"
    )
    scene_last_frames: dict = Field(
        default_factory=dict, description="各场景末帧 {scene_id: 路径}"
    )

    # === 质量控制 ===
    quality_reports: dict = Field(
        default_factory=dict, description="各阶段质量报告 {stage_name: StageQualityReport}"
    )
    retry_counts: dict = Field(
        default_factory=dict, description="各阶段重试计数 {stage_key: count}"
    )

    # === 运行时元信息 ===
    current_stage: str = Field(default="init", description="当前阶段")
    error_log: List[str] = Field(default_factory=list, description="错误日志")
    progress_percent: float = Field(default=0.0, description="总进度百分比")

    def increment_retry(self, stage_key: str) -> int:
        """增加重试计数并返回当前次数"""
        current = self.retry_counts.get(stage_key, 0)
        self.retry_counts[stage_key] = current + 1
        return current + 1

    def get_retry_count(self, stage_key: str) -> int:
        """获取某阶段的重试次数"""
        return self.retry_counts.get(stage_key, 0)

    def log_error(self, message: str) -> None:
        """记录错误"""
        self.error_log.append(message)
