"""视频生成工具 — 统一封装 Kling / Runway / Pika 等视频生成 API"""

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


class VideoGenInput(BaseModel):
    prompt: str = Field(description="视频生成 Prompt（英文）")
    negative_prompt: str = Field(default="", description="Negative Prompt")
    duration_seconds: float = Field(default=5.0, description="目标时长（秒）")
    api_provider: str = Field(
        default="kling",
        description="生成 API: kling / runway / pika",
    )
    reference_image: Optional[str] = Field(
        default=None, description="角色/风格参考图 URL 或本地路径"
    )
    first_frame: Optional[str] = Field(
        default=None, description="首帧图片（用于场景连续性）"
    )
    last_frame: Optional[str] = Field(
        default=None, description="末帧图片（Runway 支持）"
    )
    style_reference: Optional[str] = Field(
        default=None, description="风格参考图"
    )
    camera_movement: Optional[str] = Field(
        default=None, description="镜头运动类型"
    )
    consistency_weight: float = Field(
        default=0.8, description="一致性权重 (0-1)"
    )
    aspect_ratio: str = Field(default="16:9", description="画面比例")
    scene_id: int = Field(default=0, description="场景编号（用于文件命名）")


class VideoGenerationTool(BaseTool):
    name: str = "video_generator"
    description: str = (
        "调用 AI 视频生成 API 生成视频片段。"
        "支持 Kling、Runway、Pika 三个提供商。"
        "可传入参考图以保持角色和风格一致性，"
        "可传入首帧/末帧图片以保持场景连续性。"
    )
    args_schema: type[BaseModel] = VideoGenInput

    def _run(
        self,
        prompt: str,
        negative_prompt: str = "",
        duration_seconds: float = 5.0,
        api_provider: str = "kling",
        reference_image: Optional[str] = None,
        first_frame: Optional[str] = None,
        last_frame: Optional[str] = None,
        style_reference: Optional[str] = None,
        camera_movement: Optional[str] = None,
        consistency_weight: float = 0.8,
        aspect_ratio: str = "16:9",
        scene_id: int = 0,
    ) -> str:
        """生成视频并返回本地文件路径"""
        logger.info(f"视频生成 [Scene {scene_id}] Provider: {api_provider}")

        # 根据 API 提供商适配请求格式
        if api_provider == "kling":
            return self._generate_kling(
                prompt, negative_prompt, duration_seconds,
                reference_image, first_frame, style_reference,
                camera_movement, consistency_weight, aspect_ratio, scene_id,
            )
        elif api_provider == "runway":
            return self._generate_runway(
                prompt, negative_prompt, duration_seconds,
                reference_image, first_frame, last_frame, scene_id,
            )
        elif api_provider == "pika":
            return self._generate_pika(
                prompt, negative_prompt, duration_seconds,
                reference_image, scene_id,
            )
        else:
            raise ValueError(f"不支持的 API 提供商: {api_provider}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=5, max=60))
    def _generate_kling(
        self,
        prompt: str,
        negative_prompt: str,
        duration: float,
        reference_image: Optional[str],
        first_frame: Optional[str],
        style_reference: Optional[str],
        camera_movement: Optional[str],
        consistency_weight: float,
        aspect_ratio: str,
        scene_id: int,
    ) -> str:
        """Kling API 视频生成"""
        payload = APIPromptAdapter.adapt_for_kling(
            prompt=prompt,
            negative_prompt=negative_prompt,
            duration=duration,
            reference_image=reference_image,
            style_reference=style_reference,
            first_frame=first_frame,
            camera_movement=camera_movement,
            consistency_weight=consistency_weight,
            aspect_ratio=aspect_ratio,
        )

        with httpx.Client(timeout=30.0) as client:
            # 提交生成任务
            response = client.post(
                f"{settings.kling_base_url}/videos/generations",
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.kling_api_key}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            task_data = response.json()
            task_id = task_data.get("data", {}).get("task_id") or task_data.get("task_id", "")

            logger.info(f"Kling 任务已提交: {task_id}")

            # 轮询等待完成
            video_url = self._poll_kling_task(client, task_id)

        # 下载视频到本地
        output_path = str(settings.temp_dir / f"scene_{scene_id:03d}_video.mp4")
        self._download_file(video_url, output_path)
        return output_path

    def _poll_kling_task(self, client: httpx.Client, task_id: str) -> str:
        """轮询 Kling 任务状态直到完成"""
        max_wait = 300  # 最大等待 5 分钟
        elapsed = 0
        interval = 5

        while elapsed < max_wait:
            time.sleep(interval)
            elapsed += interval

            resp = client.get(
                f"{settings.kling_base_url}/videos/generations/{task_id}",
                headers={"Authorization": f"Bearer {settings.kling_api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()

            status = data.get("data", {}).get("status") or data.get("status", "")

            if status == "completed":
                video_url = (
                    data.get("data", {}).get("video_url")
                    or data.get("data", {}).get("output", {}).get("video_url", "")
                )
                if video_url:
                    return video_url
                raise RuntimeError("任务完成但未返回视频 URL")

            elif status == "failed":
                error_msg = data.get("data", {}).get("error", "未知错误")
                raise RuntimeError(f"Kling 生成失败: {error_msg}")

            logger.debug(f"Kling 任务 {task_id} 状态: {status}, 已等待 {elapsed}s")

        raise RuntimeError(f"Kling 任务超时（等待 {max_wait}s）")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=5, max=60))
    def _generate_runway(
        self,
        prompt: str,
        negative_prompt: str,
        duration: float,
        reference_image: Optional[str],
        first_frame: Optional[str],
        last_frame: Optional[str],
        scene_id: int,
    ) -> str:
        """Runway Gen-3 API 视频生成"""
        payload = APIPromptAdapter.adapt_for_runway(
            prompt=prompt,
            negative_prompt=negative_prompt,
            duration=duration,
            reference_image=reference_image,
            first_frame=first_frame,
            last_frame=last_frame,
        )

        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{settings.runway_base_url}/generations",
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.runway_api_key}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            task_data = response.json()
            task_id = task_data.get("id", "")

            # 轮询等待
            video_url = self._poll_runway_task(client, task_id)

        output_path = str(settings.temp_dir / f"scene_{scene_id:03d}_video.mp4")
        self._download_file(video_url, output_path)
        return output_path

    def _poll_runway_task(self, client: httpx.Client, task_id: str) -> str:
        """轮询 Runway 任务状态"""
        max_wait = 300
        elapsed = 0
        interval = 5

        while elapsed < max_wait:
            time.sleep(interval)
            elapsed += interval

            resp = client.get(
                f"{settings.runway_base_url}/generations/{task_id}",
                headers={"Authorization": f"Bearer {settings.runway_api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()
            status = data.get("status", "")

            if status == "SUCCEEDED":
                outputs = data.get("output", [])
                if outputs:
                    return outputs[0] if isinstance(outputs, list) else outputs
                raise RuntimeError("Runway 完成但无输出")

            elif status in ("FAILED", "CANCELLED"):
                raise RuntimeError(f"Runway 生成失败: {data.get('failure', '未知')}")

        raise RuntimeError(f"Runway 任务超时（{max_wait}s）")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=5, max=60))
    def _generate_pika(
        self,
        prompt: str,
        negative_prompt: str,
        duration: float,
        reference_image: Optional[str],
        scene_id: int,
    ) -> str:
        """Pika API 视频生成"""
        payload = APIPromptAdapter.adapt_for_pika(
            prompt=prompt,
            negative_prompt=negative_prompt,
            duration=duration,
            reference_image=reference_image,
        )

        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                "https://api.pika.art/v1/generate",
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.pika_api_key}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            data = response.json()

            video_url = data.get("video_url", "")
            if not video_url:
                # Pika 可能也是异步的，需要轮询
                task_id = data.get("id", "")
                video_url = self._poll_pika_task(client, task_id)

        output_path = str(settings.temp_dir / f"scene_{scene_id:03d}_video.mp4")
        self._download_file(video_url, output_path)
        return output_path

    def _poll_pika_task(self, client: httpx.Client, task_id: str) -> str:
        """轮询 Pika 任务"""
        max_wait = 300
        elapsed = 0

        while elapsed < max_wait:
            time.sleep(5)
            elapsed += 5

            resp = client.get(
                f"https://api.pika.art/v1/generations/{task_id}",
                headers={"Authorization": f"Bearer {settings.pika_api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("status") == "completed":
                return data.get("video_url", "")
            elif data.get("status") == "failed":
                raise RuntimeError(f"Pika 生成失败")

        raise RuntimeError("Pika 任务超时")

    @staticmethod
    def _download_file(url: str, output_path: str) -> None:
        """下载远程文件到本地"""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        with httpx.Client(timeout=120.0) as client:
            with client.stream("GET", url) as response:
                response.raise_for_status()
                with open(output_path, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        f.write(chunk)

        logger.info(f"视频已下载: {output_path}")
