"""重试策略 — 渐进式重试，从微调到大改到切换 API"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from loguru import logger
from pydantic import BaseModel, Field


class RetryLevel(str, Enum):
    """重试级别"""

    SOFT = "soft"          # 微调 Prompt，提高一致性权重
    MEDIUM = "medium"      # 大幅修改 Prompt，强化约束
    HARD = "hard"          # 切换 API 提供商


class RetryAdjustment(BaseModel):
    """重试调整方案"""

    level: RetryLevel = Field(description="重试级别")
    prompt_suffix: str = Field(default="", description="追加到 Prompt 的后缀")
    negative_additions: List[str] = Field(
        default_factory=list, description="追加到 negative prompt 的内容"
    )
    consistency_weight: Optional[float] = Field(
        default=None, description="覆盖一致性权重"
    )
    api_provider: Optional[str] = Field(
        default=None, description="切换到的 API（仅 HARD 级别）"
    )
    cfg_scale_delta: float = Field(default=0.0, description="CFG Scale 调整量")
    rewrite_prompt: bool = Field(default=False, description="是否需要完全重写 Prompt")
    additional_instructions: str = Field(default="", description="给 Agent 的额外指导")


class RetryStrategy:
    """
    渐进式重试策略管理器
    
    策略逻辑：
    - 第 1 次重试（SOFT）：微调 —— 追加强一致性指令，小幅提升权重
    - 第 2 次重试（MEDIUM）：中度修改 —— 显式约束 + negative prompt 强化
    - 第 3 次重试（HARD）：切换 API —— 使用备选生成服务
    """

    # API 备选链
    API_FALLBACK_CHAIN = {
        "kling": ["runway", "pika"],
        "runway": ["kling", "pika"],
        "pika": ["kling", "runway"],
    }

    @classmethod
    def get_adjustment(
        cls,
        retry_count: int,
        current_api: str = "kling",
        quality_feedback: str = "",
    ) -> RetryAdjustment:
        """
        根据重试次数获取调整方案
        
        Args:
            retry_count: 当前是第几次重试（1-based）
            current_api: 当前使用的 API
            quality_feedback: 质量检查的反馈信息
            
        Returns:
            RetryAdjustment 调整方案
        """
        if retry_count <= 1:
            return cls._soft_adjustment(quality_feedback)
        elif retry_count == 2:
            return cls._medium_adjustment(quality_feedback)
        else:
            return cls._hard_adjustment(current_api, quality_feedback)

    @classmethod
    def _soft_adjustment(cls, feedback: str) -> RetryAdjustment:
        """
        SOFT 级别调整 — 轻微强化
        
        策略：在原 Prompt 基础上追加一致性强化语句，小幅提升权重
        """
        logger.info("重试策略: SOFT — 微调 Prompt + 轻微提升一致性权重")

        return RetryAdjustment(
            level=RetryLevel.SOFT,
            prompt_suffix=(
                ", maintaining strict visual consistency with reference, "
                "exact same character appearance, "
                "same clothing and accessories as described"
            ),
            negative_additions=[
                "inconsistent appearance",
                "different face",
                "wrong clothing",
            ],
            consistency_weight=0.88,
            cfg_scale_delta=0.5,
            additional_instructions=(
                f"上一次生成的质量反馈: {feedback}. "
                "请确保这次更严格地遵循角色描述和风格参考。"
            ),
        )

    @classmethod
    def _medium_adjustment(cls, feedback: str) -> RetryAdjustment:
        """
        MEDIUM 级别调整 — 显著强化
        
        策略：大幅强化约束，可能需要重组 Prompt 结构
        """
        logger.info("重试策略: MEDIUM — 强化约束 + 扩展 negative prompt")

        return RetryAdjustment(
            level=RetryLevel.MEDIUM,
            prompt_suffix=(
                ", CRITICAL: exact character appearance must match reference image precisely, "
                "same face structure, same hair color and style, same skin tone, "
                "same outfit in every detail, photographic consistency required"
            ),
            negative_additions=[
                "inconsistent appearance",
                "different face",
                "wrong clothing",
                "style mismatch",
                "color shift",
                "different hair",
                "wrong body proportions",
            ],
            consistency_weight=0.95,
            cfg_scale_delta=1.0,
            rewrite_prompt=False,
            additional_instructions=(
                f"质量反馈: {feedback}. "
                "这是第二次重试，必须严格保证一致性。"
                "建议：如果角色描述不够精确，请先优化描述再生成。"
            ),
        )

    @classmethod
    def _hard_adjustment(cls, current_api: str, feedback: str) -> RetryAdjustment:
        """
        HARD 级别调整 — 切换 API
        
        策略：当前 API 多次失败，切换到备选 API
        """
        fallbacks = cls.API_FALLBACK_CHAIN.get(current_api, ["runway"])
        next_api = fallbacks[0] if fallbacks else "runway"

        logger.info(f"重试策略: HARD — 切换 API: {current_api} → {next_api}")

        return RetryAdjustment(
            level=RetryLevel.HARD,
            prompt_suffix=(
                ", maintaining absolute consistency with reference images, "
                "professional quality output required"
            ),
            negative_additions=[
                "low quality",
                "inconsistent",
                "blurry",
                "artifacts",
            ],
            consistency_weight=0.9,
            api_provider=next_api,
            cfg_scale_delta=0.0,  # 不同 API 有不同的默认值，不额外调整
            additional_instructions=(
                f"前两次使用 {current_api} 均失败（反馈: {feedback}），"
                f"现在切换到 {next_api}。"
                "请根据新 API 的特性调整 Prompt 格式。"
            ),
        )

    @classmethod
    def apply_adjustment(
        cls,
        original_params: dict,
        adjustment: RetryAdjustment,
    ) -> dict:
        """
        将调整方案应用到原始生成参数上
        
        Args:
            original_params: 原始生成参数字典
            adjustment: 调整方案
            
        Returns:
            调整后的参数字典
        """
        params = original_params.copy()

        # 追加 Prompt 后缀
        if adjustment.prompt_suffix:
            params["prompt"] = params.get("prompt", "") + adjustment.prompt_suffix

        # 追加 negative prompt
        if adjustment.negative_additions:
            existing_neg = params.get("negative_prompt", "")
            additions = ", ".join(adjustment.negative_additions)
            params["negative_prompt"] = f"{existing_neg}, {additions}" if existing_neg else additions

        # 覆盖一致性权重
        if adjustment.consistency_weight is not None:
            params["consistency_weight"] = adjustment.consistency_weight

        # 调整 CFG Scale
        if adjustment.cfg_scale_delta != 0:
            current_cfg = params.get("cfg_scale", 7.0)
            params["cfg_scale"] = min(15.0, max(1.0, current_cfg + adjustment.cfg_scale_delta))

        # 切换 API
        if adjustment.api_provider:
            params["api_provider"] = adjustment.api_provider

        return params

    @classmethod
    def should_retry(cls, retry_count: int, max_retries: int = 3) -> bool:
        """判断是否应该继续重试"""
        return retry_count < max_retries

    @classmethod
    def get_strategy_summary(cls, retry_count: int) -> str:
        """获取当前重试策略的文字摘要"""
        level_map = {1: "SOFT (微调)", 2: "MEDIUM (强化)", 3: "HARD (切换API)"}
        return level_map.get(retry_count, f"HARD+ (第{retry_count}次)")
