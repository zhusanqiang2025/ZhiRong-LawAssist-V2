# backend/app/core/exceptions.py
"""
自定义异常处理器
"""
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
# from slowapi.errors import RateLimitExceeded
import logging
import os

from .responses import (
    APIResponse,
    ResponseCode,
    ValidationErrorResponse,
    ErrorDetail,
    BusinessError,
    ValidationError,
    NotFoundError,
    UnauthorizedError,
    ForbiddenError,
    RateLimitExceededError
)

logger = logging.getLogger(__name__)

async def business_exception_handler(request: Request, exc: BusinessError):
    """业务异常处理器"""
    logger.error(f"Business Error: {exc.code} - {exc.message}")
    return JSONResponse(
        status_code=400,
        content=APIResponse.error_response(
            message=exc.message,
            code=exc.code,
            data=exc.data
        ).model_dump()
    )

async def validation_exception_handler(request: Request, exc: ValidationError):
    """数据验证异常处理器"""
    logger.error(f"Validation Error: {exc.message}")

    details = []
    for error in exc.errors:
        details.append(ErrorDetail(
            field=error.get("field"),
            message=error.get("message", "数据验证失败"),
            code=error.get("code")
        ))

    return JSONResponse(
        status_code=422,
        content=ValidationErrorResponse(
            success=False,
            message="数据验证失败",
            code=ResponseCode.VALIDATION_ERROR,
            data=None,
            details=details
        ).model_dump()
    )

async def not_found_exception_handler(request: Request, exc: NotFoundError):
    """资源不存在异常处理器"""
    logger.error(f"Not Found Error: {exc.message}")
    return JSONResponse(
        status_code=404,
        content=APIResponse.error_response(
            message=exc.message,
            code=ResponseCode.NOT_FOUND
        ).model_dump()
    )

async def unauthorized_exception_handler(request: Request, exc: UnauthorizedError):
    """未授权异常处理器"""
    logger.error(f"Unauthorized Error: {exc.message}")
    return JSONResponse(
        status_code=401,
        content=APIResponse.error_response(
            message=exc.message,
            code=ResponseCode.UNAUTHORIZED
        ).model_dump()
    )

async def forbidden_exception_handler(request: Request, exc: ForbiddenError):
    """权限不足异常处理器"""
    logger.error(f"Forbidden Error: {exc.message}")
    return JSONResponse(
        status_code=403,
        content=APIResponse.error_response(
            message=exc.message,
            code=ResponseCode.FORBIDDEN
        ).model_dump()
    )

# async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """请求频率超限异常处理器"""
    logger.warning(f"Rate Limit Exceeded: {request.client.host}")

    # 获取重试时间（秒）
    retry_after = str(int(getattr(exc, 'retry_after', 60)))

    return JSONResponse(
        status_code=429,
        content=APIResponse.error_response(
            message="请求过于频繁，请稍后再试",
            code=ResponseCode.RATE_LIMIT_EXCEEDED
        ).model_dump(),
        headers={"Retry-After": retry_after}
    )

async def request_validation_exception_handler(request: Request, exc: RequestValidationError):
    """FastAPI 请求验证异常处理器"""
    logger.error(f"Request Validation Error: {exc.errors()}")

    details = []
    for error in exc.errors():
        # 构建字段路径
        field_path = " -> ".join(str(loc) for loc in error.get("loc", []))
        details.append(ErrorDetail(
            field=field_path,
            message=error.get("msg", "验证失败"),
            code=error.get("type")
        ))

    return JSONResponse(
        status_code=422,
        content=ValidationErrorResponse(
            success=False,
            message="请求数据验证失败",
            code=ResponseCode.VALIDATION_ERROR,
            data=None,
            details=details
        ).model_dump()
    )

async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP 异常处理器"""
    logger.error(f"HTTP Exception: {exc.status_code} - {exc.detail}")

    # 根据状态码映射业务状态码
    code_mapping = {
        400: ResponseCode.BUSINESS_ERROR,
        401: ResponseCode.UNAUTHORIZED,
        403: ResponseCode.FORBIDDEN,
        404: ResponseCode.NOT_FOUND,
        429: ResponseCode.RATE_LIMIT_EXCEEDED,
        500: ResponseCode.INTERNAL_SERVER_ERROR,
        502: ResponseCode.SERVICE_UNAVAILABLE,
        503: ResponseCode.SERVICE_UNAVAILABLE,
        504: ResponseCode.TIMEOUT_ERROR
    }

    business_code = code_mapping.get(exc.status_code, ResponseCode.BUSINESS_ERROR)

    # ✅ 兼容处理：确保 message 是字符串
    if isinstance(exc.detail, dict):
        # 如果 detail 是 dict，尝试提取 message 字段
        message = exc.detail.get("message") or exc.detail.get("detail") or str(exc.detail)
    else:
        message = str(exc.detail)

    return JSONResponse(
        status_code=exc.status_code,
        content=APIResponse.error_response(
            message=message,
            code=business_code
        ).model_dump()
    )

async def general_exception_handler(request: Request, exc: Exception):
    """通用异常处理器"""
    logger.error(f"Unhandled Exception: {type(exc).__name__} - {str(exc)}", exc_info=True)

    # 生产环境下隐藏详细错误信息
    message = "服务器内部错误" if os.getenv("ENVIRONMENT") == "production" else str(exc)

    return JSONResponse(
        status_code=500,
        content=APIResponse.error_response(
            message=message,
            code=ResponseCode.INTERNAL_SERVER_ERROR
        ).model_dump()
    )

def setup_exception_handlers(app):
    """设置异常处理器"""
    # 自定义异常处理器
    app.add_exception_handler(BusinessError, business_exception_handler)
    app.add_exception_handler(ValidationError, validation_exception_handler)
    app.add_exception_handler(NotFoundError, not_found_exception_handler)
    app.add_exception_handler(UnauthorizedError, unauthorized_exception_handler)
    app.add_exception_handler(ForbiddenError, forbidden_exception_handler)
    # app.add_exception_handler(RateLimitExceededError, rate_limit_exceeded_handler)

    # FastAPI 内置异常处理器
    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
    # app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)

    logger.info("Exception handlers configured successfully")