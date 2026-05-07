"""
情绪 → 制作参数映射器

将 EmotionPoint 的三维数值 (tension, valence, energy) 映射到具体的制作参数：
  - 镜头参数：景别推荐、运镜速度、手持感强度
  - 配音参数：语速倍率、音量增益、情感标签
  - 音乐参数：BPM 建议区间、调式偏好、编曲密度
  - 调色参数：饱和度偏移、对比度偏移、色温偏移
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from src.emotion.curve import EmotionCurve, EmotionPoint


# ============================================================
# 映射输出数据结构
# ============================================================


@dataclass
class CameraParams:
    """镜头参数建议"""

    preferred_shot_types: List[str]  # 推荐景别
    camera_speed: float  # 运镜速度 0-1 (0=静止, 1=快速)
    handheld_intensity: float  # 手持感强度 0-1
    depth_of_field: str  # "shallow" / "medium" / "deep"


@dataclass
class VoiceParams:
    """配音参数建议"""

    speed_multiplier: float  # 语速倍率 (0.7~1.5)
    volume_gain_db: float  # 音量增益 (-3~6)
    emotion_tag: str  # 情感标签 (给 TTS 引擎)
    pitch_shift: float  # 音调偏移 (-2~2 半音)
    pause_weight: float  # 停顿权重 (0.5~2.0, >1 表示更多停顿)


@dataclass
class MusicParams:
    """音乐参数建议"""

    bpm_range: Tuple[int, int]  # BPM 建议区间
    mode: str  # "major" / "minor" / "mixed"
    density: float  # 编曲密度 0-1 (0=极简, 1=满编)
    dynamics: str  # "pianissimo" / "piano" / "mezzo" / "forte" / "fortissimo"
    instruments_hint: str  # 乐器建议


@dataclass
class ColorGradingParams:
    """调色参数建议"""

    saturation_offset: float  # 饱和度偏移 -0.3~0.3
    contrast_offset: float  # 对比度偏移 -0.3~0.3
    temperature_offset: float  # 色温偏移 (负=冷, 正=暖) -0.5~0.5
    brightness_offset: float  # 亮度偏移 -0.2~0.2
    vignette_strength: float  # 暗角强度 0~1


@dataclass
class SceneProductionParams:
    """单场景完整制作参数包"""

    scene_id: int
    emotion: EmotionPoint
    camera: CameraParams
    voice: VoiceParams
    music: MusicParams
    color_grading: ColorGradingParams


# ============================================================
# 映射器实现
# ============================================================


class EmotionToParamsMapper:
    """情绪 → 制作参数映射器"""

    def map_scene(self, point: EmotionPoint) -> SceneProductionParams:
        """将单个情绪点映射为完整制作参数包"""
        return SceneProductionParams(
            scene_id=point.scene_id,
            emotion=point,
            camera=self._map_camera(point),
            voice=self._map_voice(point),
            music=self._map_music(point),
            color_grading=self._map_color_grading(point),
        )

    def map_curve(self, curve: EmotionCurve) -> List[SceneProductionParams]:
        """将全片情绪曲线映射为各场景制作参数"""
        return [self.map_scene(p) for p in curve.points]

    # ================================================================
    # 镜头映射
    # ================================================================

    def _map_camera(self, point: EmotionPoint) -> CameraParams:
        t, v, e = point.tension, point.valence, point.energy

        # 高张力 → 特写 + 快速运镜 + 手持
        # 低张力 → 全景 + 缓慢运镜 + 稳定
        if t > 0.7:
            shots = ["close_up", "extreme_close_up", "over_shoulder"]
        elif t > 0.4:
            shots = ["medium", "medium_close", "close_up"]
        else:
            shots = ["wide", "extreme_wide", "medium"]

        camera_speed = 0.2 + e * 0.6 + t * 0.2  # 能量和张力驱动运镜速度
        handheld = t * 0.7 + e * 0.3  # 张力主导手持感
        handheld = min(1.0, handheld)

        # 景深：情绪聚焦时浅景深，平和时深景深
        if t > 0.6 or (e > 0.6 and abs(v) > 0.5):
            dof = "shallow"
        elif t < 0.3 and e < 0.3:
            dof = "deep"
        else:
            dof = "medium"

        return CameraParams(
            preferred_shot_types=shots,
            camera_speed=min(1.0, camera_speed),
            handheld_intensity=handheld,
            depth_of_field=dof,
        )

    # ================================================================
    # 配音映射
    # ================================================================

    def _map_voice(self, point: EmotionPoint) -> VoiceParams:
        t, v, e = point.tension, point.valence, point.energy

        # 语速：能量高 → 加速；低能量且负面 → 减速
        speed = 1.0 + (e - 0.5) * 0.4 + t * 0.1
        speed = max(0.7, min(1.5, speed))

        # 音量：能量驱动
        volume_gain = (e - 0.5) * 6.0  # -3~3 db
        volume_gain = max(-3.0, min(6.0, volume_gain))

        # 情感标签
        if v > 0.5 and e > 0.5:
            emotion_tag = "cheerful"
        elif v > 0.3:
            emotion_tag = "warm"
        elif v < -0.5:
            emotion_tag = "sad"
        elif t > 0.7:
            emotion_tag = "urgent"
        elif t > 0.4:
            emotion_tag = "serious"
        else:
            emotion_tag = "calm"

        # 音调：紧张时略高，悲伤时略低
        pitch_shift = t * 1.0 + v * 0.5 - 0.5
        pitch_shift = max(-2.0, min(2.0, pitch_shift))

        # 停顿：低能量 + 高张力时停顿多（悬念感）
        pause_weight = 1.0 + (1.0 - e) * 0.5 + t * 0.3
        pause_weight = max(0.5, min(2.0, pause_weight))

        return VoiceParams(
            speed_multiplier=round(speed, 2),
            volume_gain_db=round(volume_gain, 1),
            emotion_tag=emotion_tag,
            pitch_shift=round(pitch_shift, 1),
            pause_weight=round(pause_weight, 2),
        )

    # ================================================================
    # 音乐映射
    # ================================================================

    def _map_music(self, point: EmotionPoint) -> MusicParams:
        t, v, e = point.tension, point.valence, point.energy

        # BPM：能量驱动
        bpm_low = int(60 + e * 80)  # 60~140
        bpm_high = bpm_low + 20

        # 调式：正面 → 大调，负面 → 小调
        if v > 0.3:
            mode = "major"
        elif v < -0.3:
            mode = "minor"
        else:
            mode = "mixed"

        # 编曲密度：能量 + 张力驱动
        density = e * 0.6 + t * 0.4
        density = max(0.0, min(1.0, density))

        # 力度
        combined_intensity = e * 0.7 + t * 0.3
        if combined_intensity > 0.8:
            dynamics = "fortissimo"
        elif combined_intensity > 0.6:
            dynamics = "forte"
        elif combined_intensity > 0.4:
            dynamics = "mezzo"
        elif combined_intensity > 0.2:
            dynamics = "piano"
        else:
            dynamics = "pianissimo"

        # 乐器建议
        if t > 0.7:
            instruments = "strings tremolo, timpani, brass stabs"
        elif e > 0.7 and v > 0:
            instruments = "full orchestra, bright brass, driving percussion"
        elif v < -0.3 and e < 0.4:
            instruments = "solo piano, cello, ambient pads"
        elif e < 0.3:
            instruments = "soft strings, gentle piano, ambient textures"
        else:
            instruments = "strings ensemble, woodwinds, light percussion"

        return MusicParams(
            bpm_range=(bpm_low, bpm_high),
            mode=mode,
            density=round(density, 2),
            dynamics=dynamics,
            instruments_hint=instruments,
        )

    # ================================================================
    # 调色映射
    # ================================================================

    def _map_color_grading(self, point: EmotionPoint) -> ColorGradingParams:
        t, v, e = point.tension, point.valence, point.energy

        # 饱和度：正面情绪 → 高饱和；负面紧张 → 低饱和/去饱和
        saturation = v * 0.2 + e * 0.1
        saturation = max(-0.3, min(0.3, saturation))

        # 对比度：高张力 → 高对比度
        contrast = t * 0.25 - 0.05
        contrast = max(-0.3, min(0.3, contrast))

        # 色温：正面 → 暖色调；负面 → 冷色调
        temperature = v * 0.3 + (e - 0.5) * 0.1
        temperature = max(-0.5, min(0.5, temperature))

        # 亮度：悲伤/紧张 → 暗；快乐 → 亮
        brightness = v * 0.1 + (1.0 - t) * 0.05 - 0.05
        brightness = max(-0.2, min(0.2, brightness))

        # 暗角：高张力 → 强暗角（聚焦注意力）
        vignette = t * 0.7
        vignette = max(0.0, min(1.0, vignette))

        return ColorGradingParams(
            saturation_offset=round(saturation, 3),
            contrast_offset=round(contrast, 3),
            temperature_offset=round(temperature, 3),
            brightness_offset=round(brightness, 3),
            vignette_strength=round(vignette, 2),
        )
