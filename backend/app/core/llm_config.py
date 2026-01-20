# backend/app/core/llm_config.py
"""
LLM 配置管理 - 集中管理所有模型实例

提供统一的 LLM 配置接口，支持多种模型：
- Qwen3-235B-Thinking: 用于框架生成
- DeepSeek-R1-0528: 用于内容填充
- 默认模型: 当前使用的配置
"""
import os
import logging
from typing import Optional
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


def get_qwen3_thinking_llm() -> ChatOpenAI:
    """
    获取 Qwen3-235B-Thinking 模型（用于框架生成）

    配置：QWEN3_THINKING_* 环境变量
    - API URL: https://sd4a58h819ma6giel1ck0.apigateway-cn-beijing.volceapi.com/v1
    - Model: Qwen3-235B-A22B-Thinking-2507
    - Timeout: 120s

    Returns:
        ChatOpenAI: Qwen3-235B-Thinking 模型实例

    Raises:
        ValueError: 当缺少必需的环境变量时
    """
    api_key = os.getenv("QWEN3_THINKING_API_KEY")
    api_url = os.getenv("QWEN3_THINKING_API_URL")
    model_name = os.getenv("QWEN3_THINKING_MODEL", "Qwen3-235B-A22B-Thinking-2507")
    timeout = int(os.getenv("QWEN3_THINKING_TIMEOUT", "120"))

    if not api_key:
        raise ValueError("缺少必需的环境变量: QWEN3_THINKING_API_KEY")

    if not api_url:
        raise ValueError("缺少必需的环境变量: QWEN3_THINKING_API_URL")

    logger.info(f"[LLMConfig] 初始化 Qwen3-235B-Thinking 模型: {model_name}")

    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=api_url,
        temperature=0.3,
        request_timeout=timeout,
        max_tokens=16000,  # 支持长合同生成
        max_retries=2
    )


def get_qwen_llm() -> ChatOpenAI:
    """
    获取 Qwen 模型（用于案件分析模块）

    使用 Qwen3-235B 模型，temperature=0 确保输出确定性

    Returns:
        ChatOpenAI: Qwen 模型实例
    """
    api_key = os.getenv("QWEN3_THINKING_API_KEY")
    api_url = os.getenv("QWEN3_THINKING_API_URL")
    model_name = os.getenv("QWEN3_THINKING_MODEL", "Qwen3-235B-A22B-Thinking-2507")

    if not api_key:
        logger.warning("[LLMConfig] 未配置 QWEN3_THINKING_API_KEY，尝试使用 DEEPSEEK_API_KEY")
        api_key = os.getenv("DEEPSEEK_API_KEY")
        api_url = os.getenv("DEEPSEEK_API_URL")
        model_name = "DeepSeek-R1-0528"

    if not api_key:
        logger.warning("[LLMConfig] 未配置任何 LLM API Key")
        return None

    logger.info(f"[LLMConfig] 初始化 Qwen 模型用于案件分析: {model_name}")

    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=api_url,
        temperature=0,  # 确保输出确定性
        request_timeout=120,
        max_tokens=16000,
        max_retries=2
    )


def get_deepseek_llm() -> ChatOpenAI:
    """
    获取 DeepSeek-R1 模型（用于内容填充）

    配置：DEEPSEEK_* 环境变量
    - Model: DeepSeek-R1-0528
    - Timeout: 60s

    Returns:
        ChatOpenAI: DeepSeek-R1 模型实例

    Raises:
        ValueError: 当缺少必需的环境变量时
    """
    api_key = os.getenv("DEEPSEEK_API_KEY")
    api_url = os.getenv("DEEPSEEK_API_URL")
    model_name = os.getenv("MODEL_NAME", "DeepSeek-R1-0528")

    if not api_key:
        raise ValueError("缺少必需的环境变量: DEEPSEEK_API_KEY")

    if not api_url:
        raise ValueError("缺少必需的环境变量: DEEPSEEK_API_URL")

    logger.info(f"[LLMConfig] 初始化 DeepSeek-R1 模型: {model_name}")

    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=api_url,
        temperature=0.5,
        request_timeout=60,
        max_tokens=16000,  # 支持长合同生成
        max_retries=3
    )


def get_default_llm() -> ChatOpenAI:
    """
    获取默认 LLM（当前使用的配置）

    配置：OPENAI_* 环境变量
    - Model: deepseek-chat
    - Base URL: https://api.deepseek.com/v1

    Returns:
        ChatOpenAI: 默认模型实例

    Raises:
        ValueError: 当缺少必需的环境变量时
    """
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_API_BASE", "https://api.deepseek.com/v1")

    if not api_key:
        logger.warning("[LLMConfig] 缺少 OPENAI_API_KEY，尝试使用 DEEPSEEK_API_KEY")
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("缺少必需的环境变量: OPENAI_API_KEY 或 DEEPSEEK_API_KEY")

    logger.info("[LLMConfig] 初始化默认 LLM: deepseek-chat")

    return ChatOpenAI(
        model="deepseek-chat",
        api_key=api_key,
        base_url=base_url,
        temperature=0.3,
        max_tokens=16000  # 支持长合同生成
    )


def get_ai_postprocess_llm() -> ChatOpenAI:
    """
    获取 AI 文档预处理模型

    配置：AI_POSTPROCESS_* 环境变量
    - Model: qwen3-vl:32b-thinking-q8_0
    - 用于: PDF 文档分析、页码识别等

    Returns:
        ChatOpenAI: AI 预处理模型实例
    """
    api_key = os.getenv("AI_POSTPROCESS_API_KEY")
    api_url = os.getenv("AI_POSTPROCESS_API_URL")
    model_name = os.getenv("AI_POSTPROCESS_MODEL", "qwen3-vl:32b-thinking-q8_0")
    timeout = int(os.getenv("AI_POSTPROCESS_TIMEOUT", "30"))

    if not api_key:
        raise ValueError("缺少必需的环境变量: AI_POSTPROCESS_API_KEY")

    if not api_url:
        raise ValueError("缺少必需的环境变量: AI_POSTPROCESS_API_URL")

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
    - API URL: http://101.126.134.56:11434/v1/completions
    - Model: GPT-OSS-120B
    - 注意: 该模型不需要 API Key

    Returns:
        ChatOpenAI: GPT-OSS-120B 模型实例

    Raises:
        ValueError: 当缺少必需的环境变量时
    """
    api_url = os.getenv("GPT_OSS_120B_API_URL")
    model_name = os.getenv("GPT_OSS_120B_MODEL", "GPT-OSS-120B")

    if not api_url:
        raise ValueError("缺少必需的环境变量: GPT_OSS_120B_API_URL")

    logger.info(f"[LLMConfig] 初始化 GPT-OSS-120B 模型: {model_name}")

    return ChatOpenAI(
        model=model_name,
        api_key="dummy-key",  # Ollama 不需要真实的 API Key
        base_url=api_url,
        temperature=0.4,
        request_timeout=90,
        max_tokens=16000,  # 支持长合同生成
        max_retries=2
    )


# 模型配置验证
def validate_llm_config() -> dict:
    """
    验证所有 LLM 配置是否完整

    Returns:
        dict: 配置验证结果
        {
            "qwen3_thinking": bool,  # Qwen3 是否可用
            "deepseek": bool,        # DeepSeek 是否可用
            "default": bool,         # 默认模型是否可用
            "ai_postprocess": bool,  # AI 预处理模型是否可用
            "gpt_oss": bool,         # GPT-OSS 是否可用
            "two_stage_ready": bool, # 两阶段生成是否就绪
            "multi_model_planning_ready": bool  # 多模型规划是否就绪
        }
    """
    result = {
        "qwen3_thinking": bool(os.getenv("QWEN3_THINKING_API_KEY") and os.getenv("QWEN3_THINKING_API_URL")),
        "deepseek": bool(os.getenv("DEEPSEEK_API_KEY") and os.getenv("DEEPSEEK_API_URL")),
        "default": bool(os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY")),
        "ai_postprocess": bool(os.getenv("AI_POSTPROCESS_API_KEY") and os.getenv("AI_POSTPROCESS_API_URL")),
        "gpt_oss": bool(os.getenv("GPT_OSS_120B_API_URL")),  # GPT-OSS 只需要 URL
    }

    # 两阶段生成需要 Qwen3 和 DeepSeek 都可用
    result["two_stage_ready"] = result["qwen3_thinking"] and result["deepseek"]

    # 多模型规划需要至少 2 个模型可用（GPT-OSS + 其他任一）
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
