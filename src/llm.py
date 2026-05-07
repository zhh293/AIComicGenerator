"""LLM 配置工厂 — 统一管理 LLM 实例创建，支持 DeepSeek/OpenAI 兼容接口"""

from __future__ import annotations

from crewai import LLM

from src.config import settings


def get_llm() -> LLM:
    """
    获取配置好的 LLM 实例
    
    CrewAI 使用 LiteLLM 作为底层，支持通过 openai/ 前缀 + base_url 
    接入任何 OpenAI 兼容的 API 端点（如 DeepSeek）。
    
    配置来源：config/api_keys.env
    - OPENAI_API_KEY: API 密钥
    - OPENAI_API_BASE: API 端点 (默认 https://api.deepseek.com)
    - OPENAI_MODEL_NAME: 模型名 (默认 deepseek-chat)
    """
    model_name = settings.openai_model_name
    base_url = settings.openai_api_base
    api_key = settings.openai_api_key

    # 如果不是标准 OpenAI 端点，需要加 openai/ 前缀让 LiteLLM 识别
    if "deepseek" in base_url:
        litellm_model = f"deepseek/{model_name}"
    elif "openai.com" in base_url:
        litellm_model = model_name  # 原生 OpenAI 不需要前缀
    else:
        # 其他 OpenAI 兼容端点（如自部署的 vLLM、Ollama 等）
        litellm_model = f"openai/{model_name}"

    return LLM(
        model=litellm_model,
        base_url=base_url,
        api_key=api_key,
        temperature=0.7,
    )
