# backend/app/core/responses.py
"""
统一的API响应格式模块
"""
from typing import Any, Generic, Optional, TypeVar, Union
from pydantic import BaseModel, Field
from enum import Enum

T = TypeVar('T')

class ResponseCode(str, Enum):
    """API响应状态码枚举"""
    SUCCESS = "SUCCESS"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"
    BUSINESS_ERROR = "BUSINESS_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"

class APIResponse(BaseModel, Generic[T]):
    """
    统一的API响应格式
    """
    success: bool = Field(..., description="请求是否成功")
    message: str = Field(..., description="响应消息")
    code: ResponseCode = Field(..., description="业务状态码")
    data: Optional[T] = Field(None, description="响应数据")
    timestamp: Optional[float] = Field(None, description="响应时间戳")

    @classmethod
    def success_response(
        cls,
        data: Optional[T] = None,
        message: str = "操作成功",
        code: ResponseCode = ResponseCode.SUCCESS
    ) -> "APIResponse[T]":
        """创建成功响应"""
        import time
        return cls(
            success=True,
            message=message,
            code=code,
            data=data,
            timestamp=time.time()
        )

    @classmethod
    def error_response(
        cls,
        message: str,
        code: ResponseCode = ResponseCode.INTERNAL_SERVER_ERROR,
        data: Optional[T] = None
    ) -> "APIResponse[T]":
        """创建错误响应"""
        import time
        return cls(
            success=False,
            message=message,
            code=code,
            data=data,
            timestamp=time.time()
        )

class PaginatedResponse(BaseModel, Generic[T]):
    """
    分页响应格式
    """
    success: bool = Field(..., description="请求是否成功")
    message: str = Field(..., description="响应消息")
    code: ResponseCode = Field(..., description="业务状态码")
    data: list[T] = Field(..., description="数据列表")
    pagination: dict = Field(..., description="分页信息")
    timestamp: Optional[float] = Field(None, description="响应时间戳")

    @classmethod
    def create(
        cls,
        data: list[T],
        total: int,
        page: int,
        page_size: int,
        message: str = "查询成功"
    ) -> "PaginatedResponse[T]":
        """创建分页响应"""
        import time
        return cls(
            success=True,
            message=message,
            code=ResponseCode.SUCCESS,
            data=data,
            pagination={
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size,
                "has_next": page * page_size < total,
                "has_prev": page > 1
            },
            timestamp=time.time()
        )

class ErrorDetail(BaseModel):
    """错误详情"""
    field: Optional[str] = Field(None, description="错误字段")
    message: str = Field(..., description="错误消息")
    code: Optional[str] = Field(None, description="错误代码")

class ValidationErrorResponse(APIResponse[None]):
    """验证错误响应"""
    details: list[ErrorDetail] = Field(default_factory=list, description="错误详情列表")

class BusinessError(Exception):
    """业务异常基类"""
    def __init__(
        self,
        message: str,
        code: ResponseCode = ResponseCode.BUSINESS_ERROR,
        data: Any = None
    ):
        self.message = message
        self.code = code
        self.data = data
        super().__init__(message)

class ValidationError(Exception):
    """数据验证异常"""
    def __init__(self, message: str, errors: list[dict] = None):
        self.message = message
        self.errors = errors or []
        super().__init__(message)

class NotFoundError(Exception):
    """资源不存在异常"""
    def __init__(self, message: str = "资源不存在"):
        self.message = message
        super().__init__(message)

class UnauthorizedError(Exception):
    """未授权异常"""
    def __init__(self, message: str = "未授权访问"):
        self.message = message
        super().__init__(message)

class ForbiddenError(Exception):
    """权限不足异常"""
    def __init__(self, message: str = "权限不足"):
        self.message = message
        super().__init__(message)

class RateLimitExceededError(Exception):
    """请求频率超限异常"""
    def __init__(self, message: str = "请求过于频繁"):
        self.message = message
        super().__init__(message)