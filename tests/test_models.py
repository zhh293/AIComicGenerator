"""基础模型测试 — 验证 Pydantic 模型的创建和序列化"""

import sys
from pathlib import Path

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.flow.state import (
    Character,
    CharacterAppearance,
    CharacterOutfit,
    FilmProjectState,
    Scene,
    Screenplay,
    StyleType,
)


def test_character_creation():
    """测试角色模型创建"""
    appearance = CharacterAppearance(
        age=25,
        gender="female",
        ethnicity="East Asian",
        skin_tone="#F5DEB3",
        height_cm=165,
        build="slender",
        hair_style="long straight with bangs",
        hair_color="black #1a1a1a",
        eye_color="dark brown #3D2B1F",
        distinctive_features=["small mole below left eye"],
    )
    outfit = CharacterOutfit(
        main_clothing="white linen dress with floral embroidery",
        accessories=["silver pendant necklace"],
        shoes="white canvas sneakers",
        color_palette=["#FFFFFF", "#F0F0F0", "#C0C0C0"],
    )
    character = Character(
        name="Lin Mei",
        appearance=appearance,
        outfit=outfit,
        personality="Quiet, introspective, kind-hearted",
        voice_description="Soft, warm female voice with gentle tone",
    )

    assert character.name == "Lin Mei"
    assert character.appearance.age == 25
    assert "mole" in character.appearance.distinctive_features[0]

    # 测试 to_visual_prompt
    prompt = character.to_visual_prompt(expression="smiling", pose="walking")
    assert "Lin Mei" in prompt
    assert "25-year-old" in prompt
    assert "smiling" in prompt


def test_film_project_state():
    """测试项目状态模型"""
    state = FilmProjectState(
        user_prompt="一个孤独机器人寻找最后一朵花的故事",
        style=StyleType.CYBERPUNK,
        target_duration_seconds=60.0,
    )

    assert state.user_prompt == "一个孤独机器人寻找最后一朵花的故事"
    assert state.style == StyleType.CYBERPUNK
    assert state.target_duration_seconds == 60.0
    assert state.current_stage == "init"
    assert state.progress_percent == 0.0

    # 测试 retry 功能
    count = state.increment_retry("screenplay")
    assert count == 1
    assert state.get_retry_count("screenplay") == 1

    count = state.increment_retry("screenplay")
    assert count == 2


def test_style_presets():
    """测试风格预设加载"""
    from src.style.presets import STYLE_PRESETS

    assert len(STYLE_PRESETS) == 5
    assert "cinematic" in STYLE_PRESETS
    assert "anime" in STYLE_PRESETS
    assert "cyberpunk" in STYLE_PRESETS
    assert "ink_wash" in STYLE_PRESETS
    assert "realistic" in STYLE_PRESETS

    cinematic = STYLE_PRESETS["cinematic"]
    assert cinematic.display_name != ""
    assert cinematic.visual_prefix != ""
    assert cinematic.preferred_transitions is not None


def test_config_loading():
    """测试配置加载"""
    from src.config import settings

    assert settings.openai_model_name == "deepseek-chat"
    assert settings.openai_api_base == "https://api.deepseek.com"
    assert settings.openai_api_key.startswith("sk-")
    assert settings.video_api_provider in ("kling", "runway", "pika")
    assert settings.max_retries >= 1
    assert settings.max_concurrent_projects >= 1


def test_api_schemas():
    """测试 API Schema"""
    from src.api.schemas import CreateProjectRequest, StyleOption

    req = CreateProjectRequest(
        prompt="一段关于时光旅行的短片",
        style=StyleOption.ANIME,
        duration=45.0,
    )

    assert req.prompt == "一段关于时光旅行的短片"
    assert req.style == StyleOption.ANIME
    assert req.duration == 45.0
    assert req.language == "zh"  # default


if __name__ == "__main__":
    test_character_creation()
    print("PASS: test_character_creation")

    test_film_project_state()
    print("PASS: test_film_project_state")

    test_style_presets()
    print("PASS: test_style_presets")

    test_config_loading()
    print("PASS: test_config_loading")

    test_api_schemas()
    print("PASS: test_api_schemas")

    print("\nAll tests passed!")
