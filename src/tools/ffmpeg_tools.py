"""FFmpeg 工具集 — 视频拼接、音频混合、字幕烧录、帧提取、调色"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import List, Optional

from crewai.tools import BaseTool
from loguru import logger
from pydantic import BaseModel, Field

from src.config import settings


def _run_ffmpeg(args: List[str], description: str = "") -> subprocess.CompletedProcess:
    """统一的 FFmpeg 命令执行器"""
    cmd = [settings.ffmpeg_path] + args
    logger.info(f"FFmpeg [{description}]: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 分钟超时
            check=True,
        )
        return result
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg 执行失败: {e.stderr}")
        raise RuntimeError(f"FFmpeg error: {e.stderr[:500]}") from e
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"FFmpeg 命令超时（{description}）")


# ============================================================
# FFmpeg 探测工具
# ============================================================


class ProbeInput(BaseModel):
    file_path: str = Field(description="要探测的媒体文件路径")


class FFmpegProbeTool(BaseTool):
    name: str = "ffmpeg_probe"
    description: str = (
        "探测媒体文件信息，获取时长、分辨率、编码格式、帧率等元数据。"
        "用于在拼接前确认各片段的格式兼容性。"
    )
    args_schema: type[BaseModel] = ProbeInput

    def _run(self, file_path: str) -> str:
        cmd = [
            settings.ffmpeg_path.replace("ffmpeg", "ffprobe"),
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            file_path,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            info = json.loads(result.stdout)

            # 提取关键信息
            duration = float(info.get("format", {}).get("duration", 0))
            streams = info.get("streams", [])

            video_stream = next((s for s in streams if s["codec_type"] == "video"), None)
            audio_stream = next((s for s in streams if s["codec_type"] == "audio"), None)

            summary = {
                "duration_seconds": duration,
                "video": None,
                "audio": None,
            }

            if video_stream:
                summary["video"] = {
                    "codec": video_stream.get("codec_name"),
                    "width": video_stream.get("width"),
                    "height": video_stream.get("height"),
                    "fps": eval(video_stream.get("r_frame_rate", "24/1")),
                }

            if audio_stream:
                summary["audio"] = {
                    "codec": audio_stream.get("codec_name"),
                    "sample_rate": audio_stream.get("sample_rate"),
                    "channels": audio_stream.get("channels"),
                }

            return json.dumps(summary, indent=2)
        except Exception as e:
            return f"探测失败: {str(e)}"


# ============================================================
# 帧提取工具
# ============================================================


class FrameExtractInput(BaseModel):
    video_path: str = Field(description="视频文件路径")
    mode: str = Field(
        default="both",
        description="提取模式: first / last / both / keyframes",
    )
    output_dir: Optional[str] = Field(default=None, description="输出目录")


class FFmpegFrameExtractTool(BaseTool):
    name: str = "ffmpeg_frame_extract"
    description: str = (
        "从视频中提取关键帧。支持提取首帧、末帧、或两者。"
        "用于一致性检查和场景连续性管理。"
    )
    args_schema: type[BaseModel] = FrameExtractInput

    def _run(
        self,
        video_path: str,
        mode: str = "both",
        output_dir: Optional[str] = None,
    ) -> str:
        out_dir = Path(output_dir) if output_dir else settings.temp_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        video_name = Path(video_path).stem
        results = {}

        if mode in ("first", "both"):
            first_frame_path = str(out_dir / f"{video_name}_first_frame.png")
            _run_ffmpeg(
                [
                    "-y", "-i", video_path,
                    "-vf", "select=eq(n\\,0)",
                    "-frames:v", "1",
                    "-q:v", "2",
                    first_frame_path,
                ],
                description=f"提取首帧: {video_name}",
            )
            results["first_frame"] = first_frame_path

        if mode in ("last", "both"):
            last_frame_path = str(out_dir / f"{video_name}_last_frame.png")
            _run_ffmpeg(
                [
                    "-y", "-sseof", "-0.1",
                    "-i", video_path,
                    "-frames:v", "1",
                    "-q:v", "2",
                    last_frame_path,
                ],
                description=f"提取末帧: {video_name}",
            )
            results["last_frame"] = last_frame_path

        if mode == "keyframes":
            keyframe_pattern = str(out_dir / f"{video_name}_kf_%03d.png")
            _run_ffmpeg(
                [
                    "-y", "-i", video_path,
                    "-vf", "select=eq(pict_type\\,I)",
                    "-vsync", "vfr",
                    "-q:v", "2",
                    keyframe_pattern,
                ],
                description=f"提取关键帧: {video_name}",
            )
            results["keyframes_pattern"] = keyframe_pattern

        return json.dumps(results)


# ============================================================
# 视频拼接工具
# ============================================================


class ConcatInput(BaseModel):
    video_paths: List[str] = Field(description="按顺序排列的视频路径列表")
    transitions: List[str] = Field(
        default_factory=list,
        description="相邻视频之间的转场类型（fade/dissolve/wipeleft 等）",
    )
    transition_duration: float = Field(default=0.5, description="转场时长（秒）")
    output_path: Optional[str] = Field(default=None, description="输出路径")


class FFmpegConcatTool(BaseTool):
    name: str = "ffmpeg_concat"
    description: str = (
        "将多个视频片段拼接为一个完整视频。"
        "支持简单拼接（无转场）和带 xfade 转场效果的拼接。"
        "转场类型支持: fade, dissolve, wipeleft, wiperight, slideup, "
        "slidedown, pixelize, circleopen, circleclose"
    )
    args_schema: type[BaseModel] = ConcatInput

    def _run(
        self,
        video_paths: List[str],
        transitions: List[str] = None,
        transition_duration: float = 0.5,
        output_path: Optional[str] = None,
    ) -> str:
        if not video_paths:
            return "错误：视频列表为空"

        if len(video_paths) == 1:
            return video_paths[0]

        if output_path is None:
            output_path = str(settings.output_dir / "concat_output.mp4")

        if not transitions:
            return self._simple_concat(video_paths, output_path)
        else:
            return self._xfade_concat(video_paths, transitions, transition_duration, output_path)

    def _simple_concat(self, video_paths: List[str], output_path: str) -> str:
        """无转场快速拼接（要求所有视频格式一致）"""
        list_file = str(settings.temp_dir / "concat_list.txt")
        with open(list_file, "w") as f:
            for path in video_paths:
                f.write(f"file '{path}'\n")

        _run_ffmpeg(
            ["-y", "-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy", output_path],
            description="简单拼接",
        )
        return output_path

    def _xfade_concat(
        self,
        video_paths: List[str],
        transitions: List[str],
        duration: float,
        output_path: str,
    ) -> str:
        """带 xfade 转场的拼接"""
        # 首先获取每个视频的时长
        durations = []
        for vpath in video_paths:
            probe_tool = FFmpegProbeTool()
            info = json.loads(probe_tool._run(file_path=vpath))
            durations.append(info["duration_seconds"])

        # 构建 filter_complex
        n = len(video_paths)
        video_filter_parts = []
        audio_filter_parts = []

        # 计算每个转场的 offset（前面所有视频时长之和减去已有转场时长）
        offsets = []
        cumulative = 0.0
        for i in range(n - 1):
            cumulative += durations[i]
            offset = cumulative - duration * (i + 1)
            offsets.append(max(0, offset))

        # 逐步构建 xfade 链
        prev_v_label = "[0:v]"
        prev_a_label = "[0:a]"

        for i in range(1, n):
            transition = transitions[i - 1] if i - 1 < len(transitions) else "fade"
            offset = offsets[i - 1]

            out_v = f"[v{i}]" if i < n - 1 else "[outv]"
            out_a = f"[a{i}]" if i < n - 1 else "[outa]"

            video_filter_parts.append(
                f"{prev_v_label}[{i}:v]xfade=transition={transition}"
                f":duration={duration}:offset={offset:.3f}{out_v}"
            )
            audio_filter_parts.append(
                f"{prev_a_label}[{i}:a]acrossfade=d={duration}{out_a}"
            )

            prev_v_label = out_v
            prev_a_label = out_a

        filter_complex = ";".join(video_filter_parts + audio_filter_parts)

        cmd_args = ["-y"]
        for vpath in video_paths:
            cmd_args.extend(["-i", vpath])
        cmd_args.extend([
            "-filter_complex", filter_complex,
            "-map", "[outv]",
            "-map", "[outa]",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "18",
            "-c:a", "aac",
            "-b:a", "192k",
            output_path,
        ])

        _run_ffmpeg(cmd_args, description="xfade 转场拼接")
        return output_path


# ============================================================
# 音频混合工具
# ============================================================


class AudioMixInput(BaseModel):
    video_path: str = Field(description="视频文件路径")
    bgm_path: Optional[str] = Field(default=None, description="背景音乐路径")
    narration_path: Optional[str] = Field(default=None, description="旁白/对话音频路径")
    sfx_paths: List[str] = Field(default_factory=list, description="音效文件路径列表")
    bgm_volume: float = Field(default=0.25, description="背景音乐音量 (0-1)")
    narration_volume: float = Field(default=1.0, description="旁白音量 (0-1)")
    sfx_volume: float = Field(default=0.6, description="音效音量 (0-1)")
    output_path: Optional[str] = Field(default=None, description="输出路径")
    duck_bgm_on_narration: bool = Field(
        default=True, description="旁白时自动降低背景音乐音量"
    )


class FFmpegAudioMixTool(BaseTool):
    name: str = "ffmpeg_audio_mix"
    description: str = (
        "混合多轨音频到视频中。支持背景音乐、旁白、音效的分层混合，"
        "可设置各轨音量，并支持旁白时自动压低背景音乐(ducking)。"
    )
    args_schema: type[BaseModel] = AudioMixInput

    def _run(
        self,
        video_path: str,
        bgm_path: Optional[str] = None,
        narration_path: Optional[str] = None,
        sfx_paths: List[str] = None,
        bgm_volume: float = 0.25,
        narration_volume: float = 1.0,
        sfx_volume: float = 0.6,
        output_path: Optional[str] = None,
        duck_bgm_on_narration: bool = True,
    ) -> str:
        if output_path is None:
            output_path = str(settings.output_dir / "mixed_audio.mp4")

        sfx_paths = sfx_paths or []

        # 构建输入列表
        inputs = ["-y", "-i", video_path]
        filter_parts = []
        audio_labels = []
        input_idx = 1  # 0 是视频

        # 背景音乐
        if bgm_path:
            inputs.extend(["-i", bgm_path])
            # 循环背景音乐以匹配视频长度，并设置音量
            filter_parts.append(
                f"[{input_idx}:a]aloop=loop=-1:size=2e+09,"
                f"volume={bgm_volume}[bgm]"
            )
            audio_labels.append("[bgm]")
            input_idx += 1

        # 旁白/对话
        if narration_path:
            inputs.extend(["-i", narration_path])
            filter_parts.append(
                f"[{input_idx}:a]volume={narration_volume}[narr]"
            )
            audio_labels.append("[narr]")
            input_idx += 1

        # 音效
        for sfx_path in sfx_paths:
            inputs.extend(["-i", sfx_path])
            label = f"[sfx{input_idx}]"
            filter_parts.append(
                f"[{input_idx}:a]volume={sfx_volume}{label}"
            )
            audio_labels.append(label)
            input_idx += 1

        if not audio_labels:
            # 没有额外音频，直接复制
            _run_ffmpeg(
                ["-y", "-i", video_path, "-c", "copy", output_path],
                description="无额外音频，直接复制",
            )
            return output_path

        # 混合所有音轨
        n_tracks = len(audio_labels)
        mix_input = "".join(audio_labels)
        filter_parts.append(
            f"{mix_input}amix=inputs={n_tracks}:duration=first"
            f":dropout_transition=2[mixed]"
        )

        # 如果视频本身有音频，也混入
        filter_parts_str = ";".join(filter_parts)
        final_filter = f"{filter_parts_str};[0:a][mixed]amix=inputs=2:duration=first[aout]"

        cmd_args = inputs + [
            "-filter_complex", final_filter,
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            output_path,
        ]

        _run_ffmpeg(cmd_args, description="多轨音频混合")
        return output_path


# ============================================================
# 字幕烧录工具
# ============================================================


class SubtitleBurnInput(BaseModel):
    video_path: str = Field(description="视频路径")
    subtitle_path: Optional[str] = Field(default=None, description="SRT 字幕文件路径")
    subtitle_text: Optional[str] = Field(
        default=None, description="直接传入 SRT 内容（如果没有文件）"
    )
    font_name: str = Field(default="Arial", description="字体名")
    font_size: int = Field(default=22, description="字号")
    font_color: str = Field(default="&H00FFFFFF", description="字体颜色 ASS 格式")
    outline_color: str = Field(default="&H00000000", description="描边颜色")
    outline_width: int = Field(default=2, description="描边宽度")
    position: str = Field(default="bottom", description="位置: bottom / top / center")
    output_path: Optional[str] = Field(default=None, description="输出路径")


class FFmpegSubtitleTool(BaseTool):
    name: str = "ffmpeg_subtitle_burn"
    description: str = (
        "将字幕（SRT格式）烧录到视频画面中。"
        "支持自定义字体、大小、颜色、描边和位置。"
    )
    args_schema: type[BaseModel] = SubtitleBurnInput

    def _run(
        self,
        video_path: str,
        subtitle_path: Optional[str] = None,
        subtitle_text: Optional[str] = None,
        font_name: str = "Arial",
        font_size: int = 22,
        font_color: str = "&H00FFFFFF",
        outline_color: str = "&H00000000",
        outline_width: int = 2,
        position: str = "bottom",
        output_path: Optional[str] = None,
    ) -> str:
        if output_path is None:
            output_path = str(settings.output_dir / "subtitled.mp4")

        # 如果传入的是文本内容，先写入文件
        if subtitle_text and not subtitle_path:
            subtitle_path = str(settings.temp_dir / "temp_subtitles.srt")
            with open(subtitle_path, "w", encoding="utf-8") as f:
                f.write(subtitle_text)

        if not subtitle_path:
            return "错误：未提供字幕文件路径或字幕内容"

        # 根据 position 计算 MarginV
        margin_v = {"bottom": 30, "center": 0, "top": 30}.get(position, 30)
        alignment = {"bottom": 2, "center": 5, "top": 8}.get(position, 2)

        # 构建 force_style
        force_style = (
            f"FontName={font_name},"
            f"FontSize={font_size},"
            f"PrimaryColour={font_color},"
            f"OutlineColour={outline_color},"
            f"Outline={outline_width},"
            f"Shadow=1,"
            f"MarginV={margin_v},"
            f"Alignment={alignment}"
        )

        # 需要转义路径中的特殊字符
        escaped_sub_path = subtitle_path.replace("\\", "/").replace(":", "\\\\:")

        vf_filter = f"subtitles={escaped_sub_path}:force_style='{force_style}'"

        _run_ffmpeg(
            [
                "-y", "-i", video_path,
                "-vf", vf_filter,
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "18",
                "-c:a", "copy",
                output_path,
            ],
            description="字幕烧录",
        )
        return output_path


# ============================================================
# 调色工具
# ============================================================


class ColorGradeInput(BaseModel):
    video_path: str = Field(description="视频路径")
    lut_file: Optional[str] = Field(default=None, description="LUT 文件路径")
    brightness: float = Field(default=0.0, description="亮度调整 (-1 to 1)")
    contrast: float = Field(default=1.0, description="对比度 (0.5 to 2.0)")
    saturation: float = Field(default=1.0, description="饱和度 (0 to 2.0)")
    gamma: float = Field(default=1.0, description="Gamma (0.5 to 2.0)")
    film_grain: float = Field(default=0.0, description="胶片颗粒强度 (0 to 1)")
    vignette: float = Field(default=0.0, description="暗角强度 (0 to 1)")
    output_path: Optional[str] = Field(default=None, description="输出路径")


class FFmpegColorGradeTool(BaseTool):
    name: str = "ffmpeg_color_grade"
    description: str = (
        "对视频进行调色处理。支持 LUT 文件应用、亮度/对比度/饱和度调整、"
        "胶片颗粒叠加和暗角效果。用于统一不同片段的视觉风格。"
    )
    args_schema: type[BaseModel] = ColorGradeInput

    def _run(
        self,
        video_path: str,
        lut_file: Optional[str] = None,
        brightness: float = 0.0,
        contrast: float = 1.0,
        saturation: float = 1.0,
        gamma: float = 1.0,
        film_grain: float = 0.0,
        vignette: float = 0.0,
        output_path: Optional[str] = None,
    ) -> str:
        if output_path is None:
            output_path = str(settings.output_dir / "color_graded.mp4")

        filters = []

        # LUT 应用
        if lut_file:
            lut_path = settings.luts_dir / lut_file if "/" not in lut_file else Path(lut_file)
            if lut_path.exists():
                filters.append(f"lut3d={lut_path}")

        # 基础调色
        if brightness != 0.0 or contrast != 1.0 or saturation != 1.0 or gamma != 1.0:
            filters.append(
                f"eq=brightness={brightness}:contrast={contrast}"
                f":saturation={saturation}:gamma={gamma}"
            )

        # 暗角
        if vignette > 0:
            # vignette 滤镜的 angle 参数控制暗角范围
            angle = 0.5 + vignette * 0.8  # 映射到合理范围
            filters.append(f"vignette=angle={angle}:mode=forward")

        if not filters:
            # 无调色需求，直接复制
            _run_ffmpeg(
                ["-y", "-i", video_path, "-c", "copy", output_path],
                description="无调色，直接复制",
            )
            return output_path

        vf = ",".join(filters)

        _run_ffmpeg(
            [
                "-y", "-i", video_path,
                "-vf", vf,
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "18",
                "-c:a", "copy",
                output_path,
            ],
            description="调色处理",
        )

        # 如果需要胶片颗粒，单独叠加（用 noise 滤镜）
        if film_grain > 0:
            grain_output = output_path.replace(".mp4", "_grain.mp4")
            strength = int(film_grain * 30)  # 映射到 0-30
            _run_ffmpeg(
                [
                    "-y", "-i", output_path,
                    "-vf", f"noise=alls={strength}:allf=t+u",
                    "-c:v", "libx264",
                    "-preset", "medium",
                    "-crf", "18",
                    "-c:a", "copy",
                    grain_output,
                ],
                description="叠加胶片颗粒",
            )
            # 替换输出
            Path(output_path).unlink(missing_ok=True)
            Path(grain_output).rename(output_path)

        return output_path
