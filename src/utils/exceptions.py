"""
自定义异常类模块

定义应用特定的异常类型。
"""

from typing import Any, Dict, Optional
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging

logger = logging.getLogger(__name__)


class ClaudeAPIError(Exception):
    """Claude API基础异常类"""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


class ClaudeProcessError(ClaudeAPIError):
    """Claude进程相关异常"""

    def __init__(self, message: str, process_exit_code: Optional[int] = None):
        super().__init__(message, "claude_process_error")
        self.process_exit_code = process_exit_code


class ValidationError(ClaudeAPIError):
    """数据验证异常"""

    def __init__(self, message: str, field: Optional[str] = None):
        super().__init__(message, "validation_error")
        self.field = field


class SessionError(ClaudeAPIError):
    """会话管理异常"""

    def __init__(self, message: str, session_id: Optional[str] = None):
        super().__init__(message, "session_error")
        self.session_id = session_id


class ConfigurationError(ClaudeAPIError):
    """配置异常"""

    def __init__(self, message: str, config_key: Optional[str] = None):
        super().__init__(message, "configuration_error")
        self.config_key = config_key


class StreamingError(ClaudeAPIError):
    """流式响应异常"""

    def __init__(self, message: str, stream_id: Optional[str] = None):
        super().__init__(message, "streaming_error")
        self.stream_id = stream_id


# OpenAI兼容的错误响应格式
def create_openai_error_response(
    message: str,
    error_type: str = "invalid_request_error",
    param: Optional[str] = None,
    code: Optional[str] = None
) -> Dict[str, Any]:
    """创建OpenAI兼容的错误响应"""
    return {
        "error": {
            "message": message,
            "type": error_type,
            "param": param,
            "code": code
        },
        "object": "error"
    }


# 异常处理器
async def claude_api_exception_handler(request: Request, exc: ClaudeAPIError):
    """Claude API异常处理器"""
    logger.error(f"Claude API Error: {exc.message}", extra={
        "error_code": exc.error_code,
        "details": exc.details,
        "path": request.url.path
    })

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=create_openai_error_response(
            message=exc.message,
            error_type=exc.error_code or "internal_server_error",
            code=exc.error_code
        )
    )


async def claude_process_exception_handler(request: Request, exc: ClaudeProcessError):
    """Claude进程异常处理器"""
    logger.error(f"Claude Process Error: {exc.message}", extra={
        "process_exit_code": exc.process_exit_code,
        "path": request.url.path
    })

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=create_openai_error_response(
            message=exc.message,
            error_type="claude_process_error",
            code=exc.process_exit_code
        )
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """请求验证异常处理器"""
    logger.warning(f"Validation Error: {exc.errors()}", extra={
        "path": request.url.path
    })

    # 提取第一个验证错误
    error_detail = exc.errors()[0] if exc.errors() else {}

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=create_openai_error_response(
            message=f"Invalid request: {error_detail.get('msg', 'Unknown validation error')}",
            error_type="invalid_request_error",
            param=error_detail.get('loc', [''])[0] if error_detail.get('loc') else None,
            code="validation_error"
        )
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP异常处理器"""
    logger.warning(f"HTTP Error: {exc.detail}", extra={
        "status_code": exc.status_code,
        "path": request.url.path
    })

    # 如果detail已经是字典（来自ErrorResponse.model_dump()），直接返回
    if isinstance(exc.detail, dict):
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.detail
        )
    
    # 否则创建标准的OpenAI错误响应
    return JSONResponse(
        status_code=exc.status_code,
        content=create_openai_error_response(
            message=str(exc.detail),
            error_type="http_error",
            code=str(exc.status_code)
        )
    )


def setup_exception_handlers(app):
    """设置异常处理器"""
    from fastapi import FastAPI

    app.add_exception_handler(ClaudeAPIError, claude_api_exception_handler)
    app.add_exception_handler(ClaudeProcessError, claude_process_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)

    logger.info("Exception handlers configured")