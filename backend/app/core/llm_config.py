# backend/app/core/llm_config.py
"""
LLM 配置管理 - 集中管理所有模型实例（使用 Settings 硬编码配置）

提供统一的 LLM 配置接口，支持多种模型：
- Qwen3-235B-Thinking: 用于框架生成
- DeepSeek: 用于内容填充
- 默认模型: 当前使用的配置
"""
import os
import logging
from typing import Optional
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


def _get_settings():
    """延迟导入 settings 以避免循环依赖"""
    from app.core.config import settings
    return settings


def get_qwen3_llm() -> ChatOpenAI:
    """
    获取 Qwen3 模型

    使用 Settings 中的 QWEN3_API_* 配置

    Returns:
        ChatOpenAI: Qwen3 模型实例
    """
    settings = _get_settings()
    api_key = settings.QWEN3_API_KEY
    api_url = settings.QWEN3_API_BASE
    model_name = settings.QWEN3_MODEL
    timeout = settings.QWEN3_TIMEOUT

    # 如果 Settings 中没有配置，尝试环境变量（兼容性）
    if not api_key:
        api_key = os.getenv("QWEN3_API_KEY")
    if not api_url:
        api_url = os.getenv("QWEN3_API_BASE")

    if not api_key:
        raise ValueError("缺少 QWEN3_API_KEY 配置")
    if not api_url:
        raise ValueError("缺少 QWEN3_API_BASE 配置")

    logger.info(f"[LLMConfig] 初始化 Qwen3 模型: {model_name}")

    # 235B 模型推理需要更长时间，增加超时
    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=api_url,
        temperature=0.3,
        request_timeout=(30, timeout),
        max_tokens=16000,
        max_retries=2
    )


def get_deepseek_llm() -> ChatOpenAI:
    """
    获取 DeepSeek 模型（用于内容填充）

    使用 Settings 中的 DEEPSEEK_* 配置

    Returns:
        ChatOpenAI: DeepSeek 模型实例
    """
    settings = _get_settings()
    api_key = settings.DEEPSEEK_API_KEY
    api_url = settings.DEEPSEEK_API_URL
    model_name = settings.DEEPSEEK_MODEL

    # 如果 Settings 中没有配置，尝试环境变量（兼容性）
    if not api_key:
        api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_url:
        api_url = os.getenv("DEEPSEEK_API_URL")

    if not api_key:
        raise ValueError("缺少 DEEPSEEK_API_KEY 配置")
    if not api_url:
        raise ValueError("缺少 DEEPSEEK_API_URL 配置")

    logger.info(f"[LLMConfig] 初始化 DeepSeek 模型: {model_name}")

    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=api_url,
        temperature=0.5,
        request_timeout=60,
        max_tokens=16000,
        max_retries=3
    )


def get_default_llm() -> ChatOpenAI:
    """
    获取默认 LLM（Qwen3）

    Returns:
        ChatOpenAI: 默认模型实例
    """
    return get_qwen3_llm()


def get_ai_postprocess_llm() -> ChatOpenAI:
    """
    获取 AI 文档预处理模型

    使用 Settings 中的 AI_POSTPROCESS_* 配置
    - 用于: PDF 文档分析、页码识别等

    Returns:
        ChatOpenAI: AI 预处理模型实例
    """
    settings = _get_settings()
    api_key = settings.AI_POSTPROCESS_API_KEY
    api_url = settings.AI_POSTPROCESS_API_URL
    model_name = settings.AI_POSTPROCESS_MODEL
    timeout = settings.AI_POSTPROCESS_TIMEOUT

    # 如果 Settings 中没有配置，尝试环境变量（兼容性）
    if not api_key:
        api_key = os.getenv("AI_POSTPROCESS_API_KEY")
    if not api_url:
        api_url = os.getenv("AI_POSTPROCESS_API_URL")

    if not api_key:
        raise ValueError("缺少 AI_POSTPROCESS_API_KEY 配置")
    if not api_url:
        raise ValueError("缺少 AI_POSTPROCESS_API_URL 配置")

    logger.info(f"[LLMConfig] 初始化 AI 预处理模型: {model_name}")

    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=api_url,
        temperature=0.2,
        request_timeout=timeout,
        max_retries=2
    )


def get_gpt_oss_llm() -> ChatOpenAI:
    """
    获取 GPT-OSS-120B 模型（用于复杂推理和合同规划）

    配置：使用 Settings 中的 GPT_OSS_120B_* 配置

    Returns:
        ChatOpenAI: GPT-OSS-120B 模型实例
    """
    settings = _get_settings()
    api_url = settings.GPT_OSS_120B_API_URL
    api_key = settings.GPT_OSS_120B_API_KEY
    model_name = settings.GPT_OSS_120B_MODEL
    timeout = settings.GPT_OSS_120B_TIMEOUT

    # 如果 Settings 中没有配置，尝试环境变量（兼容性）
    if not api_url:
        api_url = os.getenv("GPT_OSS_120B_API_URL", "http://101.126.134.56:11434/v1")
    if not api_key:
        api_key = os.getenv("GPT_OSS_120B_API_KEY", "dummy-key")
    if not model_name:
        model_name = os.getenv("GPT_OSS_120B_MODEL", "gpt-oss-120b")

    logger.info(f"[LLMConfig] 初始化 GPT-OSS-120B 模型: {model_name}")

    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=api_url,
        temperature=0.4,
        request_timeout=timeout,
        max_tokens=16000,
        max_retries=2
    )


def get_assistant_model() -> ChatOpenAI:
    """
    Tier 1: 律师助理模型 (Fast)
    
    用于: 意图识别、简单交互、分类
    配额: 32B参数 / 快速响应
    """
    settings = _get_settings()
    api_key = settings.ASSISTANT_MODEL_API_KEY
    api_url = settings.ASSISTANT_MODEL_API_URL
    model_name = settings.ASSISTANT_MODEL_NAME
    timeout = settings.ASSISTANT_MODEL_TIMEOUT
    
    # 兼容性检查
    if not api_key:
        api_key = os.getenv("AI_POSTPROCESS_API_KEY") # Fallback to existing key if not set
    if not api_url:
        api_url = os.getenv("AI_POSTPROCESS_API_URL")

    logger.info(f"[LLMConfig] 初始化助理模型 (Tier 1): {model_name}")
    
    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=api_url,
        temperature=0.3, 
        request_timeout=timeout,
        max_retries=2
    )


def get_specialist_model() -> ChatOpenAI:
    """
    Tier 2: 专业律师模型 (Smart)

    用于: 复杂法律分析、推理、建议生成
    配额: 235B参数 / 深度思考
    """
    settings = _get_settings()
    api_key = settings.SPECIALIST_MODEL_API_KEY
    api_url = settings.SPECIALIST_MODEL_API_URL
    model_name = settings.SPECIALIST_MODEL_NAME
    timeout = settings.SPECIALIST_MODEL_TIMEOUT

    # 兼容性检查
    if not api_key:
        api_key = os.getenv("QWEN3_API_KEY")
    if not api_url:
        api_url = os.getenv("QWEN3_API_BASE")

    logger.info(f"[LLMConfig] 初始化专家模型 (Tier 2): {model_name}")

    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=api_url,
        temperature=0.4,
        request_timeout=timeout,
        max_tokens=16000,
        max_retries=2
    )


def validate_llm_config() -> dict:
    """
    验证所有 LLM 配置是否完整（使用 Settings）

    Returns:
        dict: 配置验证结果
    """
    settings = _get_settings()

    # 检查配置是否为非空字符串
    def is_configured(value):
        return bool(value and str(value).strip() and value != "default-api-key-change-in-production")

    result = {
        "qwen3": is_configured(settings.QWEN3_API_KEY) and is_configured(settings.QWEN3_API_BASE),
        "deepseek": is_configured(settings.DEEPSEEK_API_KEY) and is_configured(settings.DEEPSEEK_API_URL),
        "default": is_configured(settings.QWEN3_API_KEY),
        "ai_postprocess": is_configured(settings.AI_POSTPROCESS_API_KEY) and is_configured(settings.AI_POSTPROCESS_API_URL),
        "ai_text_classification": is_configured(settings.AI_TEXT_CLASSIFICATION_API_KEY) and is_configured(settings.AI_TEXT_CLASSIFICATION_API_URL),
        "gpt_oss": is_configured(settings.GPT_OSS_120B_API_KEY) and is_configured(settings.GPT_OSS_120B_API_URL),
    }

    # 两阶段生成需要 Qwen3 和 DeepSeek 都可用
    result["two_stage_ready"] = result["qwen3"] and result["deepseek"]

    # 多模型规划需要至少 2 个模型可用
    available_count = sum([
        result["qwen3"],
        result["deepseek"],
        result["gpt_oss"]
    ])
    result["multi_model_planning_ready"] = available_count >= 2

    logger.info(f"[LLMConfig] 配置验证结果: {result}")

    return result


# 兼容性别名
get_qwen3_thinking_llm = get_qwen3_llm
get_qwen3_llm = get_qwen3_llm  # 兼容性别名（用于 health.py 等）


__all__ = [
    "get_qwen3_llm",
    "get_qwen_llm",  # 兼容性别名
    "get_qwen3_thinking_llm",  # 兼容性别名
    "get_deepseek_llm",
    "get_default_llm",
    "get_ai_postprocess_llm",
    "get_gpt_oss_llm",
    "validate_llm_config",
    "get_assistant_model",
    "get_specialist_model",
]
