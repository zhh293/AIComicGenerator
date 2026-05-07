"""风格锚定 — 用第一个成功场景的输出作为后续所有场景的风格参考"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from loguru import logger


class StyleAnchor:
    """
    风格锚定管理器
    
    核心思路：第一个场景成功生成并通过质检后，提取其代表性帧作为"风格锚点"。
    后续所有场景生成时，都将此帧作为 style_reference 传入，确保整体视觉风格一致。
    """

    def __init__(self):
        self._anchor_frame: Optional[str] = None
        self._anchor_scene_id: Optional[int] = None
        self._is_locked: bool = False

    @property
    def is_set(self) -> bool:
        """是否已设置锚点"""
        return self._anchor_frame is not None and Path(self._anchor_frame).exists()

    @property
    def anchor_frame(self) -> Optional[str]:
        """获取锚定帧路径"""
        return self._anchor_frame

    @property
    def anchor_scene_id(self) -> Optional[int]:
        """锚定帧来源的场景编号"""
        return self._anchor_scene_id

    def set_anchor(self, frame_path: str, scene_id: int) -> None:
        """
        设置风格锚点
        
        仅在未锁定时可设置。一旦锁定，后续调用会被忽略。
        这确保了整部影片的风格一致性基于同一个锚点。
        """
        if self._is_locked:
            logger.debug(f"风格锚点已锁定（来源: scene {self._anchor_scene_id}），跳过设置")
            return

        if not Path(frame_path).exists():
            logger.warning(f"锚定帧文件不存在: {frame_path}")
            return

        self._anchor_frame = frame_path
        self._anchor_scene_id = scene_id
        self._is_locked = True
        logger.info(f"风格锚点已设置并锁定: scene {scene_id} -> {frame_path}")

    def get_style_reference(self) -> Optional[str]:
        """
        获取风格参考图路径
        
        返回锚定帧路径，用于传入视频生成 API 的 style_reference 参数。
        如果尚未设置锚点，返回 None。
        """
        if self.is_set:
            return self._anchor_frame
        return None

    def reset(self) -> None:
        """重置锚点（仅在重新开始整个项目时使用）"""
        self._anchor_frame = None
        self._anchor_scene_id = None
        self._is_locked = False
        logger.info("风格锚点已重置")

    def get_status(self) -> dict:
        """获取当前状态"""
        return {
            "is_set": self.is_set,
            "is_locked": self._is_locked,
            "anchor_frame": self._anchor_frame,
            "anchor_scene_id": self._anchor_scene_id,
        }
