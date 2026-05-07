"""TTS 语音合成工具 — 基于 Edge-TTS（微软免费服务）为角色生成对话和旁白音频"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Optional

import edge_tts
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from src.config import settings


class TTSInput(BaseModel):
    text: str = Field(description="要合成的文本内容")
    voice: Optional[str] = Field(
        default=None,
        description="Edge-TTS 音色名称，如 'zh-CN-XiaoxiaoNeural'。留空则自动选择。",
    )
    character_name: Optional[str] = Field(
        default=None, description="角色名（用于文件命名）"
    )
    scene_id: int = Field(default=0, description="场景编号")
    rate: str = Field(
        default="+0%",
        description="语速调节，如 '+20%'、'-10%'",
    )
    volume: str = Field(
        default="+0%",
        description="音量调节，如 '+50%'、'-20%'",
    )
    pitch: str = Field(
        default="+0Hz",
        description="音调调节，如 '+50Hz'、'-20Hz'",
    )
    generate_subtitles: bool = Field(
        default=True,
        description="是否同时生成 SRT 字幕文件",
    )


class TTSSynthesisTool(BaseTool):
    name: str = "tts_synthesis"
    description: str = (
        "使用 Edge-TTS（微软免费 TTS 服务）将文本转换为高质量语音。"
        "支持中文、英文等多种语言，提供丰富的音色选择。"
        "完全免费、无需 API Key。"
        "适用于对话、旁白和画外音的生成。"
    )
    args_schema: type[BaseModel] = TTSInput

    # ================================================================
    # 推荐音色 — 按角色类型分类
    # ================================================================

    # 中文音色
    CHINESE_VOICES = {
        "narrator_female": "zh-CN-XiaoxiaoNeural",     # 温柔女声（最自然）
        "narrator_male": "zh-CN-YunxiNeural",          # 年轻男声
        "young_female": "zh-CN-XiaoyiNeural",          # 活泼少女
        "young_male": "zh-CN-YunjianNeural",           # 阳光男青年
        "old_male": "zh-CN-YunzeNeural",               # 沉稳中年男
        "old_female": "zh-CN-XiaochenNeural",          # 成熟女声
        "child_female": "zh-CN-XiaomoNeural",          # 可爱童声
        "storyteller": "zh-CN-YunyangNeural",          # 新闻/叙述
        "emotional_female": "zh-CN-XiaoruiNeural",     # 情感女声
    }

    # 英文音色
    ENGLISH_VOICES = {
        "narrator_female": "en-US-JennyNeural",        # 温和女声
        "narrator_male": "en-US-GuyNeural",            # 浑厚男声
        "young_female": "en-US-AriaNeural",            # 年轻女声
        "young_male": "en-US-DavisNeural",             # 年轻男声
        "old_male": "en-GB-RyanNeural",                # 英式沉稳
        "storyteller": "en-US-AndrewNeural",           # 叙述型
    }

    # 日文音色
    JAPANESE_VOICES = {
        "narrator_female": "ja-JP-NanamiNeural",
        "narrator_male": "ja-JP-KeitaNeural",
    }

    def _run(
        self,
        text: str,
        voice: Optional[str] = None,
        character_name: Optional[str] = None,
        scene_id: int = 0,
        rate: str = "+0%",
        volume: str = "+0%",
        pitch: str = "+0Hz",
        generate_subtitles: bool = True,
    ) -> str:
        """合成语音并返回音频文件路径（及可选字幕路径）"""

        # 确定音色
        if not voice:
            voice = self.CHINESE_VOICES["narrator_female"]

        # 构建输出路径
        char_tag = character_name or "narration"
        output_dir = settings.temp_dir / f"scene_{scene_id:03d}"
        output_dir.mkdir(parents=True, exist_ok=True)

        audio_path = str(output_dir / f"{char_tag}_tts.mp3")
        subtitle_path = str(output_dir / f"{char_tag}_tts.srt") if generate_subtitles else None

        # 执行异步合成
        asyncio.run(
            self._synthesize(
                text=text,
                voice=voice,
                rate=rate,
                volume=volume,
                pitch=pitch,
                audio_path=audio_path,
                subtitle_path=subtitle_path,
            )
        )

        # 构建返回结果
        result = {"audio_path": audio_path, "voice": voice, "text_length": len(text)}
        if subtitle_path and Path(subtitle_path).exists():
            result["subtitle_path"] = subtitle_path

        return json.dumps(result, ensure_ascii=False)

    async def _synthesize(
        self,
        text: str,
        voice: str,
        rate: str,
        volume: str,
        pitch: str,
        audio_path: str,
        subtitle_path: Optional[str] = None,
    ) -> None:
        """调用 edge-tts 执行合成"""
        communicate = edge_tts.Communicate(
            text=text,
            voice=voice,
            rate=rate,
            volume=volume,
            pitch=pitch,
        )

        if subtitle_path:
            # 同时生成音频和字幕
            sub_maker = edge_tts.SubMaker()
            with open(audio_path, "wb") as audio_file:
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio_file.write(chunk["data"])
                    elif chunk["type"] == "WordBoundary":
                        sub_maker.feed(chunk)

            # 写入 SRT 字幕
            srt_content = sub_maker.generate_subs()
            with open(subtitle_path, "w", encoding="utf-8") as f:
                f.write(srt_content)
        else:
            # 只生成音频
            await communicate.save(audio_path)

    @classmethod
    def get_voice_for_character(
        cls,
        gender: str = "female",
        age: str = "young",
        language: str = "zh",
    ) -> str:
        """
        根据角色特征自动推荐音色
        
        Args:
            gender: male / female
            age: young / old / child
            language: zh / en / ja
        """
        voice_map = {
            "zh": cls.CHINESE_VOICES,
            "en": cls.ENGLISH_VOICES,
            "ja": cls.JAPANESE_VOICES,
        }
        voices = voice_map.get(language, cls.CHINESE_VOICES)

        # 根据年龄和性别选择
        if age == "child":
            return voices.get("child_female", voices.get("young_female", list(voices.values())[0]))

        key = f"{'old' if age == 'old' else 'young'}_{gender}"
        if key in voices:
            return voices[key]

        # fallback 到 narrator
        fallback_key = f"narrator_{gender}"
        return voices.get(fallback_key, list(voices.values())[0])

    @classmethod
    def get_available_voices(cls) -> dict:
        """获取所有预设音色"""
        return {
            "chinese": cls.CHINESE_VOICES,
            "english": cls.ENGLISH_VOICES,
            "japanese": cls.JAPANESE_VOICES,
        }

    @staticmethod
    async def list_all_voices() -> list:
        """获取 Edge-TTS 所有可用音色列表"""
        voices = await edge_tts.list_voices()
        return [
            {
                "name": v["ShortName"],
                "gender": v["Gender"],
                "locale": v["Locale"],
            }
            for v in voices
        ]
