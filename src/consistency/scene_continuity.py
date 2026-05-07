"""场景连续性管理 — 末帧-首帧链接法 + 环境描述锁定"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional

from loguru import logger

from src.config import settings
from src.tools.ffmpeg_tools import FFmpegFrameExtractTool


class SceneContinuityManager:
    """
    场景连续性管理器
    
    两大策略：
    1. 末帧-首帧链接法：提取上一场景末帧，作为下一场景的 first_frame 约束
    2. 环境描述锁定：同一地点出现的多个场景，锁定环境描述保持一致
    """

    def __init__(self):
        self._last_frames: Dict[int, str] = {}  # {scene_id: last_frame_path}
        self._first_frames: Dict[int, str] = {}  # {scene_id: first_frame_path}
        self._environment_locks: Dict[str, str] = {}  # {location_name: locked_description}
        self._frame_extract_tool = FFmpegFrameExtractTool()

    def register_scene_video(self, scene_id: int, video_path: str) -> Dict[str, str]:
        """
        注册场景视频，提取首帧和末帧
        
        在每个场景视频生成完成后调用。
        返回提取的帧文件路径。
        """
        if not Path(video_path).exists():
            logger.error(f"视频文件不存在: {video_path}")
            return {}

        result_json = self._frame_extract_tool._run(
            video_path=video_path,
            mode="both",
            output_dir=str(settings.temp_dir / "continuity_frames"),
        )
        results = json.loads(result_json)

        if "first_frame" in results:
            self._first_frames[scene_id] = results["first_frame"]

        if "last_frame" in results:
            self._last_frames[scene_id] = results["last_frame"]
            logger.info(f"Scene {scene_id} 末帧已提取: {results['last_frame']}")

        return results

    def get_continuity_first_frame(self, current_scene_id: int) -> Optional[str]:
        """
        获取当前场景应使用的首帧参考
        
        即前一个场景的末帧，用于保证视觉连续性。
        """
        prev_scene_id = current_scene_id - 1
        frame = self._last_frames.get(prev_scene_id)

        if frame and Path(frame).exists():
            logger.debug(
                f"Scene {current_scene_id} 将使用 Scene {prev_scene_id} 末帧作为首帧参考"
            )
            return frame

        return None

    def get_last_frame(self, scene_id: int) -> Optional[str]:
        """获取指定场景的末帧"""
        return self._last_frames.get(scene_id)

    def get_first_frame(self, scene_id: int) -> Optional[str]:
        """获取指定场景的首帧"""
        return self._first_frames.get(scene_id)

    # ================================================================
    # 环境描述锁定
    # ================================================================

    def lock_environment(self, location_name: str, description: str) -> None:
        """
        锁定地点的环境描述
        
        当某个地点首次出现时，锁定其环境描述。
        后续在同一地点的场景将复用此描述，避免环境不一致。
        """
        normalized_name = location_name.strip().lower()

        if normalized_name in self._environment_locks:
            logger.debug(f"地点 '{location_name}' 环境描述已锁定，跳过")
            return

        self._environment_locks[normalized_name] = description
        logger.info(f"环境描述已锁定: {location_name}")

    def get_locked_environment(self, location_name: str) -> Optional[str]:
        """获取已锁定的环境描述"""
        normalized_name = location_name.strip().lower()
        return self._environment_locks.get(normalized_name)

    def get_environment_for_scene(
        self,
        location_name: str,
        fallback_description: str,
    ) -> str:
        """
        获取场景应使用的环境描述
        
        如果该地点已锁定，返回锁定的描述。
        否则锁定当前描述并返回。
        """
        locked = self.get_locked_environment(location_name)
        if locked:
            return locked

        # 首次出现，锁定并返回
        self.lock_environment(location_name, fallback_description)
        return fallback_description

    # ================================================================
    # 状态管理
    # ================================================================

    def get_status(self) -> dict:
        """获取管理器状态摘要"""
        return {
            "registered_scenes": len(self._last_frames),
            "last_frames": {k: v for k, v in self._last_frames.items()},
            "locked_environments": list(self._environment_locks.keys()),
        }

    def reset(self) -> None:
        """重置所有状态"""
        self._last_frames.clear()
        self._first_frames.clear()
        self._environment_locks.clear()
        logger.info("场景连续性管理器已重置")
