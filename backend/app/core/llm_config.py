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


def get_qwen3_thinking_llm() -> ChatOpenAI:
    """
    获取 Qwen3-235B-Thinking 模型（用于框架生成）

    使用 Settings 中的硬编码配置：
    - QWEN3_THINKING_API_URL
    - QWEN3_THINKING_API_KEY
    - QWEN3_THINKING_MODEL

    Returns:
        ChatOpenAI: Qwen3-235B-Thinking 模型实例
    """
    settings = _get_settings()
    api_key = settings.QWEN3_THINKING_API_KEY
    api_url = settings.QWEN3_THINKING_API_URL
    model_name = settings.QWEN3_THINKING_MODEL
    timeout = settings.QWEN3_THINKING_TIMEOUT

    # 如果 Settings 中没有配置，尝试环境变量（兼容性）
    if not api_key:
        api_key = os.getenv("QWEN3_THINKING_API_KEY")
    if not api_url:
        api_url = os.getenv("QWEN3_THINKING_API_URL")

    if not api_key:
        raise ValueError("缺少 QWEN3_THINKING_API_KEY 配置")
    if not api_url:
        raise ValueError("缺少 QWEN3_THINKING_API_URL 配置")

    logger.info(f"[LLMConfig] 初始化 Qwen3-235B-Thinking 模型: {model_name}")

    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=api_url,
        temperature=0.3,
        request_timeout=timeout,
        max_tokens=16000,
        max_retries=2
    )


def get_qwen_llm() -> ChatOpenAI:
    """
    获取 Qwen 模型（用于案件分析模块）

    使用 Qwen3-235B 模型，temperature=0 确保输出确定性

    Returns:
        ChatOpenAI: Qwen 模型实例
    """
    settings = _get_settings()
    api_key = settings.QWEN3_THINKING_API_KEY
    api_url = settings.QWEN3_THINKING_API_URL
    model_name = settings.QWEN3_THINKING_MODEL

    # 如果 Settings 中没有配置，尝试环境变量（兼容性）
    if not api_key:
        api_key = os.getenv("QWEN3_THINKING_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
    if not api_url:
        api_url = os.getenv("QWEN3_THINKING_API_URL") or os.getenv("DEEPSEEK_API_URL")

    if not api_key:
        logger.warning("[LLMConfig] 未配置任何 LLM API Key")
        return None

    logger.info(f"[LLMConfig] 初始化 Qwen 模型用于案件分析: {model_name}")

    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=api_url,
        temperature=0,
        request_timeout=120,
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
    获取默认 LLM（当前使用的配置）

    使用 Settings 中的 OPENAI_* 配置

    Returns:
        ChatOpenAI: 默认模型实例
    """
    settings = _get_settings()
    api_key = settings.OPENAI_API_KEY
    base_url = settings.OPENAI_API_BASE

    # 如果 Settings 中没有配置，尝试环境变量（兼容性）
    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
    if not base_url:
        base_url = os.getenv("OPENAI_API_BASE", "https://api.deepseek.com/v1")

    if not api_key:
        raise ValueError("缺少 OPENAI_API_KEY 配置")

    logger.info("[LLMConfig] 初始化默认 LLM")

    return ChatOpenAI(
        model=settings.OPENAI_MODEL_NAME,
        api_key=api_key,
        base_url=base_url,
        temperature=0.3,
        max_tokens=16000
    )


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

    配置：GPT_OSS_* 环境变量
    - 注意: 该模型不需要 API Key

    Returns:
        ChatOpenAI: GPT-OSS-120B 模型实例
    """
    api_url = os.getenv("GPT_OSS_120B_API_URL", "http://101.126.134.56:11434/v1/completions")
    model_name = os.getenv("GPT_OSS_120B_MODEL", "GPT-OSS-120B")

    logger.info(f"[LLMConfig] 初始化 GPT-OSS-120B 模型: {model_name}")

    return ChatOpenAI(
        model=model_name,
        api_key="dummy-key",  # Ollama 不需要真实的 API Key
        base_url=api_url,
        temperature=0.4,
        request_timeout=90,
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
        "qwen3_thinking": is_configured(settings.QWEN3_THINKING_API_KEY) and is_configured(settings.QWEN3_THINKING_API_URL),
        "deepseek": is_configured(settings.DEEPSEEK_API_KEY) and is_configured(settings.DEEPSEEK_API_URL),
        "default": is_configured(settings.OPENAI_API_KEY) or is_configured(settings.DEEPSEEK_API_KEY),
        "ai_postprocess": is_configured(settings.AI_POSTPROCESS_API_KEY) and is_configured(settings.AI_POSTPROCESS_API_URL),
        "ai_text_classification": is_configured(settings.AI_TEXT_CLASSIFICATION_API_KEY) and is_configured(settings.AI_TEXT_CLASSIFICATION_API_URL),
        "gpt_oss": bool(os.getenv("GPT_OSS_120B_API_URL")),  # GPT-OSS 只需要 URL
        "langchain": is_configured(settings.LANGCHAIN_API_KEY) and is_configured(settings.LANGCHAIN_API_BASE_URL),
    }

    # 两阶段生成需要 Qwen3 和 DeepSeek 都可用
    result["two_stage_ready"] = result["qwen3_thinking"] and result["deepseek"]

    # 多模型规划需要至少 2 个模型可用
    available_count = sum([
        result["qwen3_thinking"],
        result["deepseek"],
        result["gpt_oss"]
    ])
    result["multi_model_planning_ready"] = available_count >= 2

    logger.info(f"[LLMConfig] 配置验证结果: {result}")

    return result


__all__ = [
    "get_qwen3_thinking_llm",
    "get_qwen_llm",
    "get_deepseek_llm",
    "get_default_llm",
    "get_ai_postprocess_llm",
    "get_gpt_oss_llm",
    "validate_llm_config",
]
