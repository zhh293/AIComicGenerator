"""全局配置管理 — 基于 pydantic-settings 统一管理所有环境变量和配置项"""

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """应用配置，自动从 .env 文件和环境变量加载"""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / "config" / "api_keys.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- LLM ---
    openai_api_key: str = Field(default="", description="LLM API Key（兼容 OpenAI/DeepSeek）")
    openai_api_base: str = Field(
        default="https://api.deepseek.com",
        description="LLM API Base URL（DeepSeek/OpenAI 兼容端点）",
    )
    openai_model_name: str = Field(default="deepseek-chat", description="默认 LLM 模型")

    # --- Video Generation ---
    kling_api_key: str = Field(default="", description="Kling API Key")
    kling_base_url: str = Field(
        default="https://api.klingai.com/v1", description="Kling API Base URL"
    )

    runway_api_key: str = Field(default="", description="Runway API Key")
    runway_base_url: str = Field(
        default="https://api.runwayml.com/v1", description="Runway API Base URL"
    )

    pika_api_key: str = Field(default="", description="Pika API Key")

    # --- Image Generation ---
    image_gen_provider: str = Field(default="openai", description="图片生成提供商")
    sd_base_url: str = Field(
        default="http://localhost:7860", description="Stable Diffusion 本地服务地址"
    )

    # --- TTS (Edge-TTS, 免费无需 Key) ---
    tts_default_voice: str = Field(
        default="zh-CN-XiaoxiaoNeural", description="Edge-TTS 默认音色"
    )

    # --- Music (可选，默认关闭) ---
    enable_music_generation: bool = Field(
        default=False, description="是否启用 AI 背景音乐生成（需要 Suno API Key）"
    )
    suno_api_key: str = Field(default="", description="Suno API Key（可选）")
    suno_base_url: str = Field(
        default="https://api.suno.ai/v1", description="Suno API Base URL"
    )

    # --- System ---
    ffmpeg_path: str = Field(default="ffmpeg", description="FFmpeg 可执行文件路径")
    output_dir: Path = Field(default=PROJECT_ROOT / "output", description="输出目录")
    temp_dir: Path = Field(default=PROJECT_ROOT / "temp", description="临时文件目录")

    # --- Quality Control ---
    max_retries: int = Field(default=3, description="每阶段最大重试次数")
    quality_threshold_screenplay: float = Field(default=0.8, description="剧本质量阈值")
    quality_threshold_visual: float = Field(default=0.75, description="视觉素材质量阈值")
    quality_threshold_audio: float = Field(default=0.7, description="音频素材质量阈值")

    # --- Video Provider ---
    video_api_provider: str = Field(
        default="kling", description="视频生成 API 提供商 (kling/runway/pika)"
    )

    # --- API Server ---
    api_host: str = Field(default="0.0.0.0", description="API 服务监听地址")
    api_port: int = Field(default=8000, description="API 服务端口")
    max_concurrent_projects: int = Field(
        default=3, description="最大并发项目数"
    )

    # --- Derived Paths ---
    @property
    def luts_dir(self) -> Path:
        return PROJECT_ROOT / "luts"

    @property
    def config_dir(self) -> Path:
        return PROJECT_ROOT / "config"

    def ensure_directories(self) -> None:
        """确保必要目录存在"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.luts_dir.mkdir(parents=True, exist_ok=True)


# 全局单例
settings = Settings()
settings.ensure_directories()
