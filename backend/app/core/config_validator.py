# backend/app/core/config_validator.py
"""
配置验证模块

用于验证合同生成模块的配置完整性，特别是多模型规划功能。
"""

import logging
from typing import Dict, List, Any, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)


class ConfigValidationResult:
    """配置验证结果"""
    def __init__(self):
        self.is_valid: bool = True
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []

    def add_error(self, message: str):
        """添加错误"""
        self.is_valid = False
        self.errors.append(message)

    def add_warning(self, message: str):
        """添加警告"""
        self.warnings.append(message)

    def add_info(self, message: str):
        """添加信息"""
        self.info.append(message)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "info": self.info,
            "summary": self._get_summary()
        }

    def _get_summary(self) -> str:
        """获取摘要"""
        if self.is_valid:
            return "配置验证通过"
        else:
            return f"配置验证失败：{len(self.errors)} 个错误"


def validate_multi_model_planning_config() -> ConfigValidationResult:
    """
    验证多模型规划配置

    Returns:
        ConfigValidationResult: 验证结果对象
    """
    result = ConfigValidationResult()

    # 1. 验证必需的基础配置
    if not settings.LANGCHAIN_API_KEY:
        result.add_error("LANGCHAIN_API_KEY 未设置，多模型规划无法使用")

    if not settings.LANGCHAIN_API_BASE_URL:
        result.add_error("LANGCHAIN_API_BASE_URL 未设置，多模型规划无法使用")

    if not settings.MODEL_NAME:
        result.add_error("MODEL_NAME 未设置，多模型规划无法使用")

    # 2. 验证可选的模型配置
    # Qwen3-Thinking 模型配置
    if not settings.LANGCHAIN_API_KEY:
        result.add_warning("Qwen3-Thinking 模型未配置（LANGCHAIN_API_KEY 缺失）")

    # DeepSeek 模型配置
    if not settings.DEEPSEEK_API_KEY:
        result.add_warning("DeepSeek 模型未配置（DEEPSEEK_API_KEY 缺失）")
    if not settings.DEEPSEEK_API_URL:
        result.add_warning("DeepSeek API URL 未配置（DEEPSEEK_API_URL 缺失）")

    # GPT-OSS 模型配置
    gpt_oss_configured = bool(settings.OPENAI_API_KEY and settings.OPENAI_API_BASE)
    if not gpt_oss_configured:
        result.add_warning("GPT-OSS 模型未配置（OPENAI_API_KEY 或 OPENAI_API_BASE 缺失）")

    # 3. 统计可用模型数量
    available_models = []
    if settings.LANGCHAIN_API_KEY and settings.MODEL_NAME:
        available_models.append("Qwen3-Thinking")
    if settings.DEEPSEEK_API_KEY and settings.DEEPSEEK_API_URL:
        available_models.append("DeepSeek")
    if gpt_oss_configured:
        available_models.append("GPT-OSS")

    if len(available_models) >= 2:
        result.add_info(f"多模型规划就绪：{len(available_models)} 个模型可用 ({', '.join(available_models)})")
    elif len(available_models) == 1:
        result.add_warning(f"仅有 {available_models[0]} 模型可用，多模型规划将降级为单模型")
        result.add_info("建议配置更多模型以启用多模型规划功能")
    else:
        result.add_error("没有可用的模型配置，合同生成功能无法使用")

    # 4. 验证 Celery 配置（用于异步任务）
    if not settings.CELERY_ENABLED:
        result.add_warning("Celery 未启用，合同生成任务将同步执行（可能超时）")
        result.add_info("建议设置 CELERY_ENABLED=true 以启用异步任务处理")
    else:
        result.add_info("Celery 已启用，支持异步合同生成任务")

    # 5. 验证 RAG 服务配置（用于模板检索）
    if not settings.BGE_EMBEDDING_API_URL:
        result.add_warning("BGE 嵌入服务未配置，模板检索功能可能受限")

    # 6. 验证文件处理服务
    if not settings.MINERU_ENABLED:
        result.add_info("MinerU PDF 解析未启用，将使用基础 PDF 解析")

    if not settings.OCR_ENABLED:
        result.add_info("OCR 服务未启用，图片内容提取功能不可用")

    return result


def validate_contract_generation_config() -> ConfigValidationResult:
    """
    验证合同生成模块的完整配置

    Returns:
        ConfigValidationResult: 验证结果对象
    """
    result = ConfigValidationResult()

    # 1. 验证数据库配置
    if not settings.DATABASE_URL:
        result.add_error("DATABASE_URL 未设置，合同生成任务无法持久化")
    else:
        result.add_info("数据库配置正常，支持任务历史记录")

    # 2. 验证 Redis 配置（用于 Celery）
    if not settings.REDIS_HOST:
        result.add_warning("Redis 未配置，Celery 任务队列可能无法使用")

    # 3. 验证必需的 API 配置
    required_apis = {
        "LANGCHAIN_API_KEY": settings.LANGCHAIN_API_KEY,
        "LANGCHAIN_API_BASE_URL": settings.LANGCHAIN_API_BASE_URL,
    }

    for api_name, api_value in required_apis.items():
        if not api_value:
            result.add_error(f"{api_name} 未设置，合同生成功能无法使用")

    # 4. 验证文件上传配置
    if not settings.UPLOAD_DIR:
        result.add_warning("UPLOAD_DIR 未设置，文件上传功能可能受限")

    # 5. 验证超时配置
    if settings.DEEPSEEK_TIMEOUT < 30:
        result.add_warning("DEEPSEEK_TIMEOUT 过小，可能导致大模型请求超时")

    if settings.MINERU_API_TIMEOUT < 60:
        result.add_warning("MINERU_API_TIMEOUT 过小，可能导致 PDF 解析超时")

    # 6. 汇总配置状态
    if result.is_valid:
        result.add_info("合同生成模块配置完整，所有功能可用")
    else:
        result.add_error("合同生成模块配置不完整，部分功能不可用")

    return result


def is_multi_model_planning_ready() -> bool:
    """
    快速检查多模型规划是否就绪

    Returns:
        bool: 多模型规划是否就绪
    """
    result = validate_multi_model_planning_config()
    return result.is_valid and len([m for m in result.info if "模型可用" in m]) >= 2


def get_config_summary() -> Dict[str, Any]:
    """
    获取配置摘要信息

    Returns:
        Dict: 配置摘要
    """
    multi_model_result = validate_multi_model_planning_config()
    contract_gen_result = validate_contract_generation_config()

    return {
        "multi_model_planning": multi_model_result.to_dict(),
        "contract_generation": contract_gen_result.to_dict(),
        "overall_status": {
            "is_ready": multi_model_result.is_valid and contract_gen_result.is_valid,
            "available_models": _extract_available_models(multi_model_result.info),
            "async_enabled": settings.CELERY_ENABLED,
            "database_enabled": bool(settings.DATABASE_URL),
            "redis_enabled": bool(settings.REDIS_HOST),
        }
    }


def _extract_available_models(info_messages: List[str]) -> List[str]:
    """从信息消息中提取可用模型列表"""
    models = []
    for msg in info_messages:
        if "模型可用" in msg:
            # 提取模型名称
            for model in ["Qwen3-Thinking", "DeepSeek", "GPT-OSS"]:
                if model in msg:
                    models.append(model)
    return models


# 便捷函数
def validate_all() -> Dict[str, Any]:
    """
    验证所有配置

    Returns:
        Dict: 所有验证结果
    """
    logger.info("[ConfigValidator] 开始验证配置...")

    summary = get_config_summary()

    if summary["overall_status"]["is_ready"]:
        logger.info("[ConfigValidator] ✅ 所有配置验证通过")
    else:
        logger.warning("[ConfigValidator] ⚠️  配置验证未通过，部分功能可能受限")

        # 记录错误和警告
        for category, result in summary.items():
            if isinstance(result, dict) and "errors" in result:
                if result["errors"]:
                    logger.error(f"[ConfigValidator] {category} 错误: {result['errors']}")
                if result["warnings"]:
                    logger.warning(f"[ConfigValidator] {category} 警告: {result['warnings']}")

    return summary


if __name__ == "__main__":
    # 测试代码
    import json
    summary = validate_all()
    print(json.dumps(summary, indent=2, ensure_ascii=False))
