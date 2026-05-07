"""风格预设配置 — 定义所有内置视觉风格的完整参数"""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from src.flow.state import StyleType


class ColorPalette(BaseModel):
    """色彩方案"""

    primary: str = Field(description="主色调 HEX")
    secondary: str = Field(description="辅助色 HEX")
    accent: str = Field(description="强调色 HEX")
    shadows: str = Field(description="阴影色调 HEX")
    highlights: str = Field(description="高光色调 HEX")


class LightingPreset(BaseModel):
    """光照预设"""

    key_light: str = Field(description="主光源描述")
    fill_light: str = Field(description="补光描述")
    ambient: str = Field(description="环境光描述")
    default_time_of_day: str = Field(description="默认时间段")
    color_temperature: str = Field(default="neutral", description="色温倾向")


class CameraPreset(BaseModel):
    """镜头预设"""

    default_lens: str = Field(description="默认镜头描述")
    depth_of_field: str = Field(description="景深风格")
    movement_style: str = Field(description="运动风格")
    preferred_aspect_ratio: str = Field(default="16:9", description="画面比例")


class AudioPreset(BaseModel):
    """音频风格预设"""

    music_style: str = Field(description="背景音乐风格提示")
    music_instruments: str = Field(default="", description="主要乐器")
    voice_style: str = Field(description="配音风格")
    ambient_sound: str = Field(default="", description="环境音特征")


class StylePresetConfig(BaseModel):
    """完整风格预设配置"""

    name: str = Field(description="内部标识名")
    display_name: str = Field(description="显示名称")
    description: str = Field(description="风格描述")

    # 视觉核心
    visual_prefix: str = Field(description="注入每个 Prompt 的风格前缀")
    negative_prompt: str = Field(description="全局 negative prompt")
    color_palette: ColorPalette
    lighting: LightingPreset
    camera: CameraPreset

    # 生成参数
    preferred_api: str = Field(default="kling", description="推荐生成 API")
    cfg_scale: float = Field(default=7.0, description="Classifier-Free Guidance 强度")
    consistency_weight: float = Field(default=0.8, description="一致性权重")
    motion_intensity: float = Field(default=0.5, description="运动强度 0-1")

    # 后期参数
    lut_file: Optional[str] = Field(default=None, description="LUT 文件名")
    post_processing_filters: List[str] = Field(default_factory=list)
    film_grain_intensity: float = Field(default=0.0, description="胶片颗粒强度")
    vignette_intensity: float = Field(default=0.0, description="暗角强度")

    # 音频
    audio: AudioPreset

    # 转场
    preferred_transitions: List[str] = Field(default_factory=list)
    default_transition_duration: float = Field(default=0.5, description="默认转场时长")


# ============================================================
# 内置风格预设
# ============================================================

STYLE_PRESETS: Dict[str, StylePresetConfig] = {
    StyleType.CINEMATIC: StylePresetConfig(
        name="cinematic",
        display_name="电影质感",
        description="好莱坞电影级画面质感，强调光影层次、景深虚化和叙事氛围",
        visual_prefix=(
            "cinematic film still, shot on Arri Alexa with anamorphic lens, "
            "natural shallow depth of field, subtle film grain, "
            "professional color grading with warm tones, volumetric lighting, "
            "dramatic composition following rule of thirds, "
            "2.39:1 widescreen cinematic framing, photorealistic"
        ),
        negative_prompt=(
            "cartoon, anime, illustration, painting, low quality, blurry, "
            "oversaturated, flat lighting, amateur photography, "
            "distorted proportions, watermark, text overlay"
        ),
        color_palette=ColorPalette(
            primary="#2C3E50",
            secondary="#E67E22",
            accent="#F39C12",
            shadows="#1A252F",
            highlights="#FDE3A7",
        ),
        lighting=LightingPreset(
            key_light="warm directional sunlight from 45 degrees above",
            fill_light="soft ambient bounce light from environment",
            ambient="natural atmospheric haze with volumetric rays",
            default_time_of_day="golden hour",
            color_temperature="warm (3200K-4500K)",
        ),
        camera=CameraPreset(
            default_lens="50mm prime lens, f/1.8 aperture",
            depth_of_field="shallow, subject sharply focused with creamy bokeh background",
            movement_style="smooth dolly, crane, and steadicam movements",
            preferred_aspect_ratio="21:9",
        ),
        preferred_api="kling",
        cfg_scale=7.5,
        consistency_weight=0.85,
        motion_intensity=0.5,
        lut_file="cinematic_warm.cube",
        post_processing_filters=["film_grain", "vignette", "subtle_bloom"],
        film_grain_intensity=0.15,
        vignette_intensity=0.2,
        audio=AudioPreset(
            music_style="orchestral cinematic score, emotional and sweeping",
            music_instruments="strings, piano, french horn, percussion",
            voice_style="warm, resonant, narrative tone with measured pacing",
            ambient_sound="subtle room tone, environmental ambience",
        ),
        preferred_transitions=["dissolve", "fade", "wipeleft"],
        default_transition_duration=0.8,
    ),
    StyleType.ANIME: StylePresetConfig(
        name="anime",
        display_name="日系动漫",
        description="高品质日本动漫风格，融合新海诚的光影和吉卜力的温暖",
        visual_prefix=(
            "high quality anime key visual, detailed anime art style, "
            "cel-shaded characters with soft shading, vibrant saturated colors, "
            "extremely detailed anime background art with atmospheric perspective, "
            "soft diffused lighting with lens flare, anime color palette, "
            "Studio Ghibli warmth meets Makoto Shinkai lighting, "
            "clean lineart, expressive anime eyes"
        ),
        negative_prompt=(
            "photorealistic, 3D render, western cartoon, low quality, "
            "sketchy, unfinished, deformed anatomy, bad hands, "
            "ugly, blurry, noisy, watermark"
        ),
        color_palette=ColorPalette(
            primary="#87CEEB",
            secondary="#FFB7C5",
            accent="#FF6B6B",
            shadows="#4A4A8A",
            highlights="#FFFAF0",
        ),
        lighting=LightingPreset(
            key_light="soft overhead anime-style rim lighting",
            fill_light="reflected environmental colors with warm bounce",
            ambient="warm diffused golden glow, god rays through clouds",
            default_time_of_day="afternoon with dramatic cumulus clouds",
            color_temperature="warm to neutral",
        ),
        camera=CameraPreset(
            default_lens="wide angle for landscapes, medium for characters",
            depth_of_field="selective soft focus on character, painterly bokeh",
            movement_style="smooth pan, slow zoom, dramatic pull-back reveals",
            preferred_aspect_ratio="16:9",
        ),
        preferred_api="runway",
        cfg_scale=8.0,
        consistency_weight=0.8,
        motion_intensity=0.4,
        lut_file="anime_vibrant.cube",
        post_processing_filters=["bloom", "color_pop", "soft_glow"],
        film_grain_intensity=0.0,
        vignette_intensity=0.1,
        audio=AudioPreset(
            music_style="J-pop instrumental, emotional piano and strings",
            music_instruments="piano, violin, acoustic guitar, flute",
            voice_style="expressive, emotional, clear enunciation",
            ambient_sound="gentle wind, birds, school bells",
        ),
        preferred_transitions=["fade", "wiperight", "slideup"],
        default_transition_duration=0.5,
    ),
    StyleType.CYBERPUNK: StylePresetConfig(
        name="cyberpunk",
        display_name="赛博朋克",
        description="霓虹闪烁的未来都市，高科技与低生活，暗黑氛围与彩色光污染",
        visual_prefix=(
            "cyberpunk aesthetic, neon-lit dystopian cityscape, "
            "rain-soaked reflective streets, holographic advertisements floating, "
            "dark moody atmosphere with vivid neon accents, "
            "high contrast chiaroscuro lighting, blue and magenta neon glow, "
            "futuristic technology and augmented reality overlays, "
            "Blade Runner 2049 meets Ghost in the Shell, "
            "cinematic night photography, volumetric fog"
        ),
        negative_prompt=(
            "bright cheerful, nature scenes, pastoral, medieval, fantasy, "
            "low quality, simple flat colors, cartoon, childish, "
            "well-lit daytime, clean sterile"
        ),
        color_palette=ColorPalette(
            primary="#0D0221",
            secondary="#FF00FF",
            accent="#00FFFF",
            shadows="#050010",
            highlights="#FF1493",
        ),
        lighting=LightingPreset(
            key_light="neon sign spill light in magenta and cyan",
            fill_light="reflected neon from wet surfaces and puddles",
            ambient="dark atmospheric fog with scattered neon penetration",
            default_time_of_day="perpetual night",
            color_temperature="cold blue with warm neon accents",
        ),
        camera=CameraPreset(
            default_lens="wide angle for cityscapes, telephoto for surveillance feel",
            depth_of_field="deep focus for city, shallow for character isolation",
            movement_style="handheld kinetic, drone sweeps, dutch angles",
            preferred_aspect_ratio="21:9",
        ),
        preferred_api="kling",
        cfg_scale=8.5,
        consistency_weight=0.82,
        motion_intensity=0.6,
        lut_file="cyberpunk_neon.cube",
        post_processing_filters=[
            "chromatic_aberration",
            "neon_glow",
            "scan_lines",
            "rain_overlay",
        ],
        film_grain_intensity=0.1,
        vignette_intensity=0.3,
        audio=AudioPreset(
            music_style="synthwave, dark electronic, industrial ambient",
            music_instruments="synthesizers, drum machines, distorted bass, glitch effects",
            voice_style="gritty noir narration, world-weary detective tone",
            ambient_sound="rain, distant sirens, electronic hum, crowd murmur",
        ),
        preferred_transitions=["pixelize", "slideup", "fade"],
        default_transition_duration=0.4,
    ),
    StyleType.INK_WASH: StylePresetConfig(
        name="ink_wash",
        display_name="水墨中国风",
        description="传统中国水墨画韵味，留白写意，东方哲学美学",
        visual_prefix=(
            "traditional Chinese ink wash painting, shuimo art style, "
            "elegant flowing brush strokes on rice paper texture, "
            "muted earth tones with selective cinnabar red accent, "
            "misty mountain landscape atmosphere, philosophical serenity, "
            "generous negative space and white space composition, "
            "Song dynasty landscape painting aesthetic, "
            "ink bleeding and diffusion effects, calligraphic energy"
        ),
        negative_prompt=(
            "photorealistic, western oil painting, vivid neon colors, "
            "modern technology, busy cluttered composition, "
            "3D render, anime style, digital art look"
        ),
        color_palette=ColorPalette(
            primary="#2C2C2C",
            secondary="#8B7355",
            accent="#8B0000",
            shadows="#1A1A1A",
            highlights="#F5F5DC",
        ),
        lighting=LightingPreset(
            key_light="soft diffused mountain light filtering through mist",
            fill_light="atmospheric fog as natural light diffuser",
            ambient="ethereal dreamlike atmospheric perspective",
            default_time_of_day="early morning mist or dusk",
            color_temperature="neutral to cool",
        ),
        camera=CameraPreset(
            default_lens="wide contemplative compositions, vertical scroll framing",
            depth_of_field="atmospheric perspective as primary depth cue",
            movement_style="slow meditative horizontal scroll panning",
            preferred_aspect_ratio="16:9",
        ),
        preferred_api="runway",
        cfg_scale=7.0,
        consistency_weight=0.75,
        motion_intensity=0.3,
        lut_file="ink_wash_muted.cube",
        post_processing_filters=["paper_texture", "ink_bleed", "desaturate_partial"],
        film_grain_intensity=0.05,
        vignette_intensity=0.0,
        audio=AudioPreset(
            music_style="traditional Chinese classical, contemplative and sparse",
            music_instruments="guqin, bamboo flute (dizi), pipa, erhu",
            voice_style="calm poetic narration, contemplative scholarly tone",
            ambient_sound="mountain stream, wind in bamboo, distant temple bell",
        ),
        preferred_transitions=["dissolve", "fade"],
        default_transition_duration=1.2,
    ),
    StyleType.REALISTIC: StylePresetConfig(
        name="realistic",
        display_name="写实纪录",
        description="高清写实风格，接近纪录片质感，自然光线和真实色彩",
        visual_prefix=(
            "photorealistic, ultra high definition, shot on RED camera, "
            "natural lighting, true-to-life colors, "
            "documentary style cinematography, sharp focus, "
            "8K resolution quality, realistic skin textures, "
            "natural environment, no post-processing stylization"
        ),
        negative_prompt=(
            "stylized, cartoon, anime, painting, illustration, "
            "over-processed, HDR overdone, unrealistic colors, "
            "artificial lighting, CGI look"
        ),
        color_palette=ColorPalette(
            primary="#4A5568",
            secondary="#718096",
            accent="#2D3748",
            shadows="#1A202C",
            highlights="#F7FAFC",
        ),
        lighting=LightingPreset(
            key_light="natural available light, sun or overcast sky",
            fill_light="natural bounce from environment surfaces",
            ambient="true-to-life atmospheric conditions",
            default_time_of_day="varies naturally",
            color_temperature="daylight balanced (5600K)",
        ),
        camera=CameraPreset(
            default_lens="35mm to 85mm range, natural perspective",
            depth_of_field="natural, varies with scene",
            movement_style="steady, professional, unobtrusive",
            preferred_aspect_ratio="16:9",
        ),
        preferred_api="kling",
        cfg_scale=6.5,
        consistency_weight=0.88,
        motion_intensity=0.5,
        lut_file=None,
        post_processing_filters=[],
        film_grain_intensity=0.0,
        vignette_intensity=0.0,
        audio=AudioPreset(
            music_style="ambient, minimal, atmospheric underscore",
            music_instruments="piano, ambient pads, subtle strings",
            voice_style="natural conversational tone, authentic",
            ambient_sound="realistic environmental audio, room tone",
        ),
        preferred_transitions=["dissolve", "fade"],
        default_transition_duration=0.6,
    ),
}


def get_style_preset(style: StyleType) -> StylePresetConfig:
    """获取风格预设配置，找不到时回退到 cinematic"""
    return STYLE_PRESETS.get(style, STYLE_PRESETS[StyleType.CINEMATIC])


def register_custom_style(style_type: str, config: StylePresetConfig) -> None:
    """注册自定义风格"""
    STYLE_PRESETS[style_type] = config
