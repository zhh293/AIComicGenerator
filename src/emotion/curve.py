"""
情绪曲线量化引擎

核心思想：将每个场景的情绪状态量化为三个独立维度的浮点数值：
  - tension (张力): 0.0 ~ 1.0  — 悬念/紧张程度
  - valence (情感极性): -1.0 ~ 1.0 — 负面↔正面情感
  - energy (能量/节奏): 0.0 ~ 1.0 — 安静↔激烈

这三个维度的组合可以映射到具体的影片制作参数：
  - 镜头：景别、运镜速度、手持晃动程度
  - 配音：语速、音量、情感色彩
  - 音乐：BPM、调式、编曲密度
  - 调色：饱和度、对比度、色温偏移
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ============================================================
# 数据模型
# ============================================================


@dataclass
class EmotionPoint:
    """单个场景的情绪量化点"""

    scene_id: int
    tension: float = 0.5  # 0-1: 平静→极度紧张
    valence: float = 0.0  # -1~1: 悲伤→快乐
    energy: float = 0.5  # 0-1: 安静→激烈

    # 可选标签，便于调试
    mood_label: str = ""

    def __post_init__(self):
        self.tension = max(0.0, min(1.0, self.tension))
        self.valence = max(-1.0, min(1.0, self.valence))
        self.energy = max(0.0, min(1.0, self.energy))


@dataclass
class EmotionCurve:
    """全片情绪曲线 — 由有序的 EmotionPoint 序列组成"""

    points: List[EmotionPoint] = field(default_factory=list)

    def add_point(self, point: EmotionPoint) -> None:
        self.points.append(point)
        self.points.sort(key=lambda p: p.scene_id)

    def get_point(self, scene_id: int) -> Optional[EmotionPoint]:
        for p in self.points:
            if p.scene_id == scene_id:
                return p
        return None

    @property
    def climax_scene_id(self) -> Optional[int]:
        """找到情绪高潮点（tension + energy 之和最高的场景）"""
        if not self.points:
            return None
        peak = max(self.points, key=lambda p: p.tension + p.energy)
        return peak.scene_id

    @property
    def emotional_range(self) -> float:
        """全片情感跨度（valence 极差）"""
        if not self.points:
            return 0.0
        vals = [p.valence for p in self.points]
        return max(vals) - min(vals)

    def get_delta(self, scene_id: int) -> Optional[Tuple[float, float, float]]:
        """获取某场景相对上一场景的情绪变化量"""
        prev = None
        for p in self.points:
            if p.scene_id == scene_id:
                if prev is None:
                    return (0.0, 0.0, 0.0)
                return (
                    p.tension - prev.tension,
                    p.valence - prev.valence,
                    p.energy - prev.energy,
                )
            prev = p
        return None


# ============================================================
# 情绪词汇 → 数值映射表
# ============================================================

# 常见 mood 关键词到 (tension, valence, energy) 的映射
MOOD_KEYWORD_MAP: Dict[str, Tuple[float, float, float]] = {
    # 正面、低能量
    "peaceful": (0.1, 0.6, 0.2),
    "serene": (0.05, 0.7, 0.15),
    "calm": (0.1, 0.4, 0.2),
    "warm": (0.15, 0.6, 0.3),
    "tender": (0.2, 0.5, 0.25),
    "nostalgic": (0.3, 0.2, 0.25),
    "melancholic": (0.3, -0.4, 0.2),
    "bittersweet": (0.35, -0.1, 0.3),
    # 正面、高能量
    "joyful": (0.1, 0.9, 0.7),
    "euphoric": (0.15, 1.0, 0.9),
    "triumphant": (0.3, 0.8, 0.85),
    "hopeful": (0.2, 0.6, 0.5),
    "inspiring": (0.25, 0.7, 0.6),
    "exciting": (0.4, 0.5, 0.8),
    # 中性
    "neutral": (0.3, 0.0, 0.4),
    "mysterious": (0.5, 0.0, 0.35),
    "contemplative": (0.3, 0.1, 0.25),
    "curious": (0.35, 0.2, 0.45),
    # 负面、低能量
    "sad": (0.2, -0.7, 0.2),
    "lonely": (0.25, -0.5, 0.15),
    "somber": (0.3, -0.4, 0.2),
    "despair": (0.4, -0.9, 0.3),
    "grief": (0.3, -0.8, 0.2),
    # 负面、高能量
    "tense": (0.75, -0.2, 0.6),
    "anxious": (0.7, -0.3, 0.55),
    "suspenseful": (0.8, -0.1, 0.5),
    "terrifying": (0.9, -0.6, 0.7),
    "angry": (0.7, -0.5, 0.8),
    "furious": (0.85, -0.7, 0.9),
    "chaotic": (0.8, -0.3, 0.95),
    # 高潮/转折
    "climactic": (0.95, 0.0, 0.9),
    "dramatic": (0.8, 0.0, 0.75),
    "shocking": (0.9, -0.2, 0.85),
    "epic": (0.7, 0.4, 0.85),
}


# ============================================================
# 情绪量化器
# ============================================================


class EmotionQuantizer:
    """
    从场景的 mood 标签自动量化为数值。
    支持组合词（如 "tense hopeful"）通过加权平均计算。
    """

    def __init__(self, keyword_map: Optional[Dict] = None):
        self.keyword_map = keyword_map or MOOD_KEYWORD_MAP

    def quantize(self, mood_text: str) -> EmotionPoint:
        """将文本 mood 描述转换为量化情绪点"""
        if not mood_text:
            return EmotionPoint(scene_id=0)

        words = mood_text.lower().replace(",", " ").replace("_", " ").split()
        matched_values: List[Tuple[float, float, float]] = []

        for word in words:
            if word in self.keyword_map:
                matched_values.append(self.keyword_map[word])
            else:
                # 尝试模糊匹配（前缀）
                for key, val in self.keyword_map.items():
                    if key.startswith(word) or word.startswith(key):
                        matched_values.append(val)
                        break

        if not matched_values:
            # 无法匹配，返回中性
            return EmotionPoint(scene_id=0, tension=0.3, valence=0.0, energy=0.4, mood_label=mood_text)

        # 加权平均
        n = len(matched_values)
        avg_tension = sum(v[0] for v in matched_values) / n
        avg_valence = sum(v[1] for v in matched_values) / n
        avg_energy = sum(v[2] for v in matched_values) / n

        return EmotionPoint(
            scene_id=0,
            tension=avg_tension,
            valence=avg_valence,
            energy=avg_energy,
            mood_label=mood_text,
        )

    def build_curve_from_scenes(self, scenes: list) -> EmotionCurve:
        """
        从 Scene 列表自动构建全片情绪曲线

        参数 scenes: List[Scene]，每个 scene 需要有 scene_id 和 mood 属性
        """
        curve = EmotionCurve()

        for scene in scenes:
            point = self.quantize(getattr(scene, "mood", "neutral"))
            point.scene_id = getattr(scene, "scene_id", 0)
            curve.add_point(point)

        return curve
