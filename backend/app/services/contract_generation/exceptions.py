"""
合同生成模块 - 错误处理和异常类

定义了合同生成过程中可能出现的各种异常类型，
以及统一的错误处理和重试机制。
"""

from typing import Optional, Dict, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)


# ==================== 错误类型定义 ====================

class ContractGenerationError(Exception):
    """合同生成基础异常类"""

    def __init__(
        self,
        message: str,
        error_code: str = "CG_GENERAL_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details
        }


class ConfigurationError(ContractGenerationError):
    """配置错误"""

    def __init__(self, message: str, missing_configs: Optional[list] = None):
        super().__init__(
            message=message,
            error_code="CG_CONFIG_ERROR",
            details={"missing_configs": missing_configs or []}
        )


class ModelServiceError(ContractGenerationError):
    """模型服务错误"""

    def __init__(
        self,
        message: str,
        model_name: Optional[str] = None,
        original_error: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            error_code="CG_MODEL_ERROR",
            details={
                "model_name": model_name,
                "original_error": str(original_error) if original_error else None
            }
        )


class MultiModelPlanningError(ContractGenerationError):
    """多模型规划错误"""

    def __init__(
        self,
        message: str,
        failed_models: Optional[list] = None,
        partial_results: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="CG_MULTIMODEL_PLANNING_ERROR",
            details={
                "failed_models": failed_models or [],
                "partial_results": partial_results
            }
        )


class DocumentProcessingError(ContractGenerationError):
    """文档处理错误"""

    def __init__(
        self,
        message: str,
        file_path: Optional[str] = None,
        processing_stage: Optional[str] = None
    ):
        super().__init__(
            message=message,
            error_code="CG_DOCUMENT_PROCESSING_ERROR",
            details={
                "file_path": file_path,
                "processing_stage": processing_stage
            }
        )


class DatabaseOperationError(ContractGenerationError):
    """数据库操作错误"""

    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        original_error: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            error_code="CG_DATABASE_ERROR",
            details={
                "operation": operation,
                "original_error": str(original_error) if original_error else None
            }
        )


class WorkflowExecutionError(ContractGenerationError):
    """工作流执行错误"""

    def __init__(
        self,
        message: str,
        node_name: Optional[str] = None,
        current_state: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="CG_WORKFLOW_ERROR",
            details={
                "node_name": node_name,
                "current_state": current_state
            }
        )


class TemplateMatchingError(ContractGenerationError):
    """模板匹配错误"""

    def __init__(
        self,
        message: str,
        contract_type: Optional[str] = None,
        available_templates: Optional[list] = None
    ):
        super().__init__(
            message=message,
            error_code="CG_TEMPLATE_MATCHING_ERROR",
            details={
                "contract_type": contract_type,
                "available_templates": available_templates or []
            }
        )


class RateLimitError(ContractGenerationError):
    """速率限制错误"""

    def __init__(
        self,
        message: str = "请求过于频繁，请稍后再试",
        retry_after: Optional[int] = None
    ):
        super().__init__(
            message=message,
            error_code="CG_RATE_LIMIT_ERROR",
            details={"retry_after": retry_after}
        )


# ==================== 错误严重级别 ====================

class ErrorSeverity(Enum):
    """错误严重级别"""
    LOW = "low"           # 低级别：可自动恢复
    MEDIUM = "medium"     # 中级别：需要降级处理
    HIGH = "high"         # 高级别：需要用户干预
    CRITICAL = "critical" # 严重：系统级故障


# ==================== 错误处理策略 ====================

class ErrorHandlingStrategy:
    """错误处理策略"""

    def __init__(
        self,
        severity: ErrorSeverity,
        retry_able: bool = False,
        max_retries: int = 0,
        fallback_to_single_model: bool = False,
        notify_user: bool = False,
        user_message: Optional[str] = None
    ):
        self.severity = severity
        self.retry_able = retry_able
        self.max_retries = max_retries
        self.fallback_to_single_model = fallback_to_single_model
        self.notify_user = notify_user
        self.user_message = user_message


# 错误类型到处理策略的映射
ERROR_STRATEGIES: Dict[type, ErrorHandlingStrategy] = {
    ConfigurationError: ErrorHandlingStrategy(
        severity=ErrorSeverity.HIGH,
        retry_able=False,
        notify_user=True,
        user_message="系统配置不完整，请联系管理员"
    ),

    ModelServiceError: ErrorHandlingStrategy(
        severity=ErrorSeverity.MEDIUM,
        retry_able=True,
        max_retries=2,
        fallback_to_single_model=True,
        notify_user=True,
        user_message="AI 模型服务暂时不可用，正在重试或使用备用方案"
    ),

    MultiModelPlanningError: ErrorHandlingStrategy(
        severity=ErrorSeverity.MEDIUM,
        retry_able=False,
        fallback_to_single_model=True,
        notify_user=False,  # 降级处理，不通知用户
        user_message="多模型规划失败，已降级到单模型模式"
    ),

    DocumentProcessingError: ErrorHandlingStrategy(
        severity=ErrorSeverity.MEDIUM,
        retry_able=True,
        max_retries=1,
        notify_user=True,
        user_message="文档处理失败，请检查文件格式是否正确"
    ),

    DatabaseOperationError: ErrorHandlingStrategy(
        severity=ErrorSeverity.HIGH,
        retry_able=True,
        max_retries=3,
        notify_user=True,
        user_message="数据库操作失败，正在重试"
    ),

    WorkflowExecutionError: ErrorHandlingStrategy(
        severity=ErrorSeverity.HIGH,
        retry_able=False,
        notify_user=True,
        user_message="合同生成流程出现异常，请重试或联系管理员"
    ),

    TemplateMatchingError: ErrorHandlingStrategy(
        severity=ErrorSeverity.LOW,
        retry_able=False,
        notify_user=False,
        user_message="未找到合适的模板，将使用通用模板"
    ),

    RateLimitError: ErrorHandlingStrategy(
        severity=ErrorSeverity.MEDIUM,
        retry_able=True,
        max_retries=1,
        notify_user=True,
        user_message="请求过于频繁，请稍后再试"
    ),
}


# ==================== 错误处理函数 ====================

def get_error_strategy(error: Exception) -> ErrorHandlingStrategy:
    """
    根据错误类型获取处理策略

    Args:
        error: 异常对象

    Returns:
        ErrorHandlingStrategy: 错误处理策略
    """
    # 查找最匹配的错误类型
    for error_type, strategy in ERROR_STRATEGIES.items():
        if isinstance(error, error_type):
            return strategy

    # 默认策略
    return ErrorHandlingStrategy(
        severity=ErrorSeverity.MEDIUM,
        retry_able=False,
        notify_user=True,
        user_message="发生未知错误，请重试或联系管理员"
    )


def handle_error(
    error: Exception,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    统一的错误处理函数

    Args:
        error: 异常对象
        context: 错误上下文信息

    Returns:
        Dict: 包含错误详情和处理建议的字典
    """
    strategy = get_error_strategy(error)

    # 记录错误日志
    log_context = context or {}
    if strategy.severity in [ErrorSeverity.MEDIUM, ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
        logger.error(
            f"[ErrorHandler] {error.__class__.__name__}: {str(error)}",
            extra={"context": log_context, "details": getattr(error, 'details', {})},
            exc_info=True
        )
    else:
        logger.warning(
            f"[ErrorHandler] {error.__class__.__name__}: {str(error)}",
            extra={"context": log_context}
        )

    # 构建错误响应
    error_response = {
        "success": False,
        "error": {
            "code": getattr(error, 'error_code', 'UNKNOWN_ERROR'),
            "message": strategy.user_message or str(error),
            "severity": strategy.severity.value,
            "retry_able": strategy.retry_able,
            "max_retries": strategy.max_retries,
            "fallback_to_single_model": strategy.fallback_to_single_model,
            "notify_user": strategy.notify_user
        }
    }

    # 如果是自定义异常，添加详细信息
    if isinstance(error, ContractGenerationError):
        error_response["error"]["details"] = error.details

    # 添加上下文信息（仅用于调试）
    if context:
        error_response["debug_context"] = {
            "context": context,
            "error_type": error.__class__.__name__
        }

    return error_response


def should_fallback_to_single_model(error: Exception) -> bool:
    """
    判断是否应该降级到单模型模式

    Args:
        error: 异常对象

    Returns:
        bool: 是否降级
    """
    strategy = get_error_strategy(error)
    return strategy.fallback_to_single_model


def is_retry_able(error: Exception) -> bool:
    """
    判断错误是否可重试

    Args:
        error: 异常对象

    Returns:
        bool: 是否可重试
    """
    strategy = get_error_strategy(error)
    return strategy.retry_able


def get_max_retries(error: Exception) -> int:
    """
    获取最大重试次数

    Args:
        error: 异常对象

    Returns:
        int: 最大重试次数
    """
    strategy = get_error_strategy(error)
    return strategy.max_retries


# ==================== 用户友好的错误消息 ====================

USER_FRIENDLY_MESSAGES = {
    "CG_CONFIG_ERROR": "系统配置不完整，请联系管理员检查配置",
    "CG_MODEL_ERROR": "AI 模型服务暂时不可用，系统正在尝试恢复",
    "CG_MULTIMODEL_PLANNING_ERROR": "多模型规划遇到问题，已自动切换到单模型模式",
    "CG_DOCUMENT_PROCESSING_ERROR": "文档处理失败，请确保上传的文件格式正确",
    "CG_DATABASE_ERROR": "数据库操作失败，请稍后重试",
    "CG_WORKFLOW_ERROR": "合同生成流程出现异常，请重试或联系管理员",
    "CG_TEMPLATE_MATCHING_ERROR": "未找到完全匹配的模板，将使用通用模板",
    "CG_RATE_LIMIT_ERROR": "请求过于频繁，请稍后再试",
    "UNKNOWN_ERROR": "发生未知错误，请重试或联系管理员"
}


def get_user_friendly_message(error_code: str) -> str:
    """
    获取用户友好的错误消息

    Args:
        error_code: 错误代码

    Returns:
        str: 用户友好的错误消息
    """
    return USER_FRIENDLY_MESSAGES.get(error_code, USER_FRIENDLY_MESSAGES["UNKNOWN_ERROR"])
