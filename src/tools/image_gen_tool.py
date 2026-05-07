"""图片生成工具 — 用于生成角色参考图、场景概念图等静态图片"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import httpx
from crewai.tools import BaseTool
from loguru import logger
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import settings
from src.style.api_adapter import APIPromptAdapter


class ImageGenInput(BaseModel):
    prompt: str = Field(description="图片生成 Prompt（英文）")
    negative_prompt: str = Field(default="", description="Negative Prompt")
    purpose: str = Field(
        default="scene",
        description="用途: character_reference / scene / style_reference",
    )
    size: str = Field(default="1920x1080", description="尺寸 WxH")
    output_filename: Optional[str] = Field(
        default=None, description="输出文件名（不含目录）"
    )


class ImageGenerationTool(BaseTool):
    name: str = "image_generator"
    description: str = (
        "生成高质量静态图片。主要用途：\n"
        "1. 角色参考图（character_reference）：生成角色全身概念图用于一致性约束\n"
        "2. 场景图（scene）：生成场景参考\n"
        "3. 风格参考图（style_reference）：生成风格基准图"
    )
    args_schema: type[BaseModel] = ImageGenInput

    def _run(
        self,
        prompt: str,
        negative_prompt: str = "",
        purpose: str = "scene",
        size: str = "1920x1080",
        output_filename: Optional[str] = None,
    ) -> str:
        """生成图片并返回本地文件路径"""
        provider = settings.image_gen_provider

        if output_filename is None:
            output_filename = f"{purpose}_{hash(prompt) % 10000:04d}.png"

        output_path = str(settings.temp_dir / output_filename)

        # 根据用途调整 Prompt
        adjusted_prompt = self._adjust_prompt_for_purpose(prompt, purpose)

        if provider == "openai":
            return self._generate_with_openai(adjusted_prompt, size, output_path)
        else:
            return self._generate_with_sd(
                adjusted_prompt, negative_prompt, size, output_path
            )

    def _adjust_prompt_for_purpose(self, prompt: str, purpose: str) -> str:
        """根据用途调整 Prompt"""
        if purpose == "character_reference":
            return (
                f"character concept art sheet, full body front view, "
                f"three-quarter view, clean white background, "
                f"high quality detailed illustration, "
                f"{prompt}"
            )
        elif purpose == "style_reference":
            return (
                f"establishing shot, wide angle, detailed environment, "
                f"high production value, {prompt}"
            )
        return prompt

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30))
    def _generate_with_openai(self, prompt: str, size: str, output_path: str) -> str:
        """使用 OpenAI DALL-E 生成"""
        payload = APIPromptAdapter.adapt_for_image_gen(
            prompt=prompt, size=size, provider="openai"
        )

        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                "https://api.openai.com/v1/images/generations",
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            data = response.json()

            image_url = data["data"][0]["url"]

        # 下载图片
        self._download_image(image_url, output_path)
        return output_path

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30))
    def _generate_with_sd(
        self, prompt: str, negative_prompt: str, size: str, output_path: str
    ) -> str:
        """使用 Stable Diffusion WebUI API 生成"""
        payload = APIPromptAdapter.adapt_for_image_gen(
            prompt=prompt,
            negative_prompt=negative_prompt,
            size=size,
            provider="sd",
        )

        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{settings.sd_base_url}/sdapi/v1/txt2img",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            # SD WebUI 返回 base64 图片
            import base64

            image_data = base64.b64decode(data["images"][0])

            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(image_data)

        logger.info(f"图片已生成 (SD): {output_path}")
        return output_path

    @staticmethod
    def _download_image(url: str, output_path: str) -> None:
        """下载图片到本地"""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        with httpx.Client(timeout=60.0) as client:
            response = client.get(url)
            response.raise_for_status()
            with open(output_path, "wb") as f:
                f.write(response.content)

        logger.info(f"图片已下载: {output_path}")
