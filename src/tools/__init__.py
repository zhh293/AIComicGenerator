"""Tools 模块 — 封装所有外部工具为 CrewAI Tool"""

from src.tools.ffmpeg_tools import (
    FFmpegConcatTool,
    FFmpegAudioMixTool,
    FFmpegSubtitleTool,
    FFmpegFrameExtractTool,
    FFmpegColorGradeTool,
    FFmpegProbeTool,
)
from src.tools.video_gen_tool import VideoGenerationTool
from src.tools.image_gen_tool import ImageGenerationTool
from src.tools.tts_tool import TTSSynthesisTool
from src.tools.music_gen_tool import MusicGenerationTool

__all__ = [
    "FFmpegConcatTool",
    "FFmpegAudioMixTool",
    "FFmpegSubtitleTool",
    "FFmpegFrameExtractTool",
    "FFmpegColorGradeTool",
    "FFmpegProbeTool",
    "VideoGenerationTool",
    "ImageGenerationTool",
    "TTSSynthesisTool",
    "MusicGenerationTool",
]
