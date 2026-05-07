"""音乐生成工具 — 基于 Suno API 生成背景音乐"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import httpx
from crewai.tools import BaseTool
from loguru import logger
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import settings
from src.style.api_adapter import APIPromptAdapter


class MusicGenInput(BaseModel):
    prompt: str = Field(
        description="音乐描述 Prompt，如 'cinematic orchestral score, emotional strings, slow tempo'"
    )
    duration_seconds: float = Field(
        default=60.0, description="目标时长（秒），最长 240 秒"
    )
    instrumental: bool = Field(
        default=True, description="是否纯器乐（无人声）"
    )
    mood: str = Field(
        default="neutral",
        description="情绪标签: happy / sad / tense / peaceful / epic / mysterious",
    )
    output_filename: Optional[str] = Field(
        default=None, description="输出文件名"
    )


class MusicGenerationTool(BaseTool):
    name: str = "music_generator"
    description: str = (
        "使用 Suno AI 生成背景音乐。支持指定风格、情绪、时长。"
        "适用于生成短片的背景配乐，支持纯器乐和带人声两种模式。"
    )
    args_schema: type[BaseModel] = MusicGenInput

    def _run(
        self,
        prompt: str,
        duration_seconds: float = 60.0,
        instrumental: bool = True,
        mood: str = "neutral",
        output_filename: Optional[str] = None,
    ) -> str:
        """生成音乐并返回本地文件路径"""
        if output_filename is None:
            output_filename = f"bgm_{mood}_{int(duration_seconds)}s.mp3"

        output_path = str(settings.temp_dir / output_filename)

        # 增强 Prompt
        enhanced_prompt = self._enhance_prompt(prompt, mood, instrumental)

        # 调用 Suno API
        music_url = self._generate_music(enhanced_prompt, duration_seconds, instrumental)

        # 下载到本地
        self._download_file(music_url, output_path)

        return output_path

    def _enhance_prompt(self, prompt: str, mood: str, instrumental: bool) -> str:
        """增强音乐 Prompt"""
        mood_descriptors = {
            "happy": "uplifting, bright, cheerful energy",
            "sad": "melancholic, bittersweet, emotional depth",
            "tense": "suspenseful, building tension, dramatic urgency",
            "peaceful": "serene, calming, meditative tranquility",
            "epic": "grand, powerful, sweeping orchestral grandeur",
            "mysterious": "enigmatic, atmospheric, curious wonder",
            "romantic": "warm, tender, intimate passion",
            "action": "high energy, driving rhythm, adrenaline",
            "neutral": "balanced, versatile underscore",
        }

        mood_desc = mood_descriptors.get(mood, mood_descriptors["neutral"])
        parts = [prompt, mood_desc]

        if instrumental:
            parts.append("purely instrumental, no vocals")

        parts.append("professional production quality, suitable for film")

        return ", ".join(parts)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=5, max=60))
    def _generate_music(self, prompt: str, duration: float, instrumental: bool) -> str:
        """调用 Suno API 生成音乐"""
        payload = APIPromptAdapter.adapt_for_suno_music(
            prompt=prompt,
            duration_seconds=duration,
            instrumental=instrumental,
        )

        with httpx.Client(timeout=30.0) as client:
            # 提交生成任务
            response = client.post(
                f"{settings.suno_base_url}/generate",
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.suno_api_key}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            task_data = response.json()

            # 获取任务 ID
            task_id = (
                task_data.get("id")
                or task_data.get("data", {}).get("task_id", "")
            )

            if not task_id:
                # 可能是同步返回
                audio_url = task_data.get("audio_url", "")
                if audio_url:
                    return audio_url
                raise RuntimeError("Suno API 未返回任务 ID 或音频 URL")

            # 轮询等待
            return self._poll_task(client, task_id)

    def _poll_task(self, client: httpx.Client, task_id: str) -> str:
        """轮询 Suno 任务状态"""
        max_wait = 300
        elapsed = 0
        interval = 8

        while elapsed < max_wait:
            time.sleep(interval)
            elapsed += interval

            resp = client.get(
                f"{settings.suno_base_url}/generations/{task_id}",
                headers={"Authorization": f"Bearer {settings.suno_api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()

            status = data.get("status", "")

            if status in ("completed", "complete"):
                audio_url = data.get("audio_url") or data.get("output_url", "")
                if audio_url:
                    return audio_url
                raise RuntimeError("Suno 任务完成但无音频 URL")

            elif status == "failed":
                raise RuntimeError(f"Suno 生成失败: {data.get('error', '未知')}")

            logger.debug(f"Suno 任务 {task_id}: {status}, 已等待 {elapsed}s")

        raise RuntimeError(f"Suno 任务超时（{max_wait}s）")

    @staticmethod
    def _download_file(url: str, output_path: str) -> None:
        """下载文件到本地"""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        with httpx.Client(timeout=120.0) as client:
            response = client.get(url)
            response.raise_for_status()
            with open(output_path, "wb") as f:
                f.write(response.content)

        logger.info(f"音乐已下载: {output_path}")
