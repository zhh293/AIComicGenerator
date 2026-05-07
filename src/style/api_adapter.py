"""API Prompt 格式适配器 — 将统一的内部 Prompt 转换为各平台 API 所需格式"""

from __future__ import annotations

from typing import Optional


class APIPromptAdapter:
    """
    适配不同视频/图片生成 API 的请求格式
    
    各 API 对 Prompt 字段名、参数名、格式要求各不相同，
    此适配器提供统一接口，按目标 API 输出对应格式。
    """

    @staticmethod
    def adapt_for_kling(
        prompt: str,
        negative_prompt: str = "",
        duration: float = 5.0,
        reference_image: Optional[str] = None,
        style_reference: Optional[str] = None,
        first_frame: Optional[str] = None,
        camera_movement: Optional[str] = None,
        consistency_weight: float = 0.8,
        aspect_ratio: str = "16:9",
    ) -> dict:
        """适配 Kling API 请求格式"""
        payload = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "mode": "professional",
            "duration": str(int(duration)),
            "aspect_ratio": aspect_ratio,
            "cfg_scale": 0.5,  # Kling 的 cfg 范围是 0-1
        }

        if reference_image:
            payload["image_reference"] = {
                "url": reference_image,
                "weight": consistency_weight,
            }

        if style_reference:
            payload["style_reference"] = {
                "url": style_reference,
                "weight": 0.6,
            }

        if first_frame:
            payload["first_frame"] = {
                "url": first_frame,
                "weight": 0.8,
            }

        if camera_movement:
            payload["camera_control"] = {
                "type": camera_movement,
                "intensity": 0.5,
            }

        return payload

    @staticmethod
    def adapt_for_runway(
        prompt: str,
        negative_prompt: str = "",
        duration: float = 4.0,
        reference_image: Optional[str] = None,
        first_frame: Optional[str] = None,
        last_frame: Optional[str] = None,
        motion_score: int = 5,
        seed: Optional[int] = None,
    ) -> dict:
        """适配 Runway Gen-3 API 请求格式"""
        payload = {
            "text_prompt": prompt,
            "seconds": min(int(duration), 10),  # Runway 上限 10s
            "motion_score": motion_score,
            "interpolate": True,
            "watermark": False,
        }

        if reference_image:
            payload["init_image"] = reference_image

        if first_frame:
            payload["first_frame_image"] = first_frame

        if last_frame:
            payload["last_frame_image"] = last_frame

        if seed is not None:
            payload["seed"] = seed

        return payload

    @staticmethod
    def adapt_for_pika(
        prompt: str,
        negative_prompt: str = "",
        duration: float = 4.0,
        reference_image: Optional[str] = None,
        cfg_scale: float = 7.0,
        motion: str = "auto",
    ) -> dict:
        """适配 Pika API 请求格式"""
        payload = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "style": "cinematic",
            "fps": 24,
            "duration": int(duration),
            "guidance_scale": cfg_scale,
            "motion": motion,
            "output_format": "mp4",
        }

        if reference_image:
            payload["image"] = reference_image

        return payload

    @staticmethod
    def adapt_for_image_gen(
        prompt: str,
        negative_prompt: str = "",
        size: str = "1920x1080",
        provider: str = "openai",
        reference_image: Optional[str] = None,
    ) -> dict:
        """适配图片生成 API 请求格式（用于角色参考图等）"""
        if provider == "openai":
            return {
                "prompt": prompt,
                "model": "dall-e-3",
                "size": _convert_size_for_dalle(size),
                "quality": "hd",
                "n": 1,
            }
        else:
            # Stable Diffusion WebUI API 格式
            width, height = size.split("x")
            payload = {
                "prompt": prompt,
                "negative_prompt": negative_prompt,
                "width": int(width),
                "height": int(height),
                "steps": 30,
                "cfg_scale": 7.0,
                "sampler_name": "DPM++ 2M Karras",
            }
            if reference_image:
                payload["init_images"] = [reference_image]
                payload["denoising_strength"] = 0.5
            return payload

    @staticmethod
    def adapt_for_edge_tts(
        text: str,
        voice: str = "zh-CN-XiaoxiaoNeural",
        rate: str = "+0%",
        volume: str = "+0%",
        pitch: str = "+0Hz",
    ) -> dict:
        """适配 Edge-TTS 合成参数"""
        return {
            "text": text,
            "voice": voice,
            "rate": rate,
            "volume": volume,
            "pitch": pitch,
        }

    @staticmethod
    def adapt_for_suno_music(
        prompt: str,
        duration_seconds: float = 60.0,
        instrumental: bool = True,
    ) -> dict:
        """适配 Suno 音乐生成 API 请求格式"""
        return {
            "prompt": prompt,
            "make_instrumental": instrumental,
            "duration": min(int(duration_seconds), 240),  # Suno 上限 4 分钟
            "output_format": "mp3",
        }


def _convert_size_for_dalle(size: str) -> str:
    """将自由尺寸转换为 DALL-E 支持的尺寸"""
    width, height = map(int, size.split("x"))
    ratio = width / height

    if ratio > 1.3:
        return "1792x1024"
    elif ratio < 0.77:
        return "1024x1792"
    else:
        return "1024x1024"
