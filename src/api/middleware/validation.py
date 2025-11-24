"""
请求验证中间件模块

提供请求数据验证和格式检查功能。
"""

import time
from typing import Callable
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
import logging

from ...models.response import ErrorResponse
from ...utils.exceptions import ValidationError

logger = logging.getLogger(__name__)


class ValidationMiddleware:
    """请求验证中间件"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # 创建Request对象
        request = Request(scope, receive)

        # 创建一个call_next函数
        async def call_next(request):
            response_sent = False

            async def send_wrapper(response):
                nonlocal response_sent
                if response_sent:
                    await send(response)
                    return

                response_sent = True
                await send(response)

            return await self.app(scope, request.receive, send_wrapper)
        # 记录请求开始时间
        start_time = time.time()

        # 验证请求头
        try:
            await self._validate_headers(request)
        except ValidationError as e:
            return self._create_validation_error_response(e)

        # 验证请求大小
        try:
            await self._validate_request_size(request)
        except ValidationError as e:
            return self._create_validation_error_response(e)

        # 验证Content-Type（对POST请求）
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                await self._validate_content_type(request)
            except ValidationError as e:
                return self._create_validation_error_response(e)

        # 处理请求
        try:
            response = await call_next(request)

            # 添加处理时间头
            process_time = time.time() - start_time
            response.headers["X-Process-Time"] = str(process_time)

            return response

        except Exception as e:
            logger.error(f"Request processing error: {e}", extra={
                "method": request.method,
                "url": str(request.url),
                "process_time": time.time() - start_time
            })
            raise

    async def _validate_headers(self, request: Request) -> None:
        """验证请求头"""
        # 验证User-Agent
        user_agent = request.headers.get("user-agent", "")
        if len(user_agent) > 500:
            raise ValidationError("User-Agent header too long", "user-agent")

        # 验证Authorization头（如果存在）
        auth_header = request.headers.get("authorization", "")
        if auth_header and len(auth_header) > 1000:
            raise ValidationError("Authorization header too long", "authorization")

    async def _validate_request_size(self, request: Request) -> None:
        """验证请求大小"""
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
                from ...utils.config import config
                if size > config.max_request_size:
                    raise ValidationError(
                        f"Request size {size} bytes exceeds maximum {config.max_request_size} bytes",
                        "content-length"
                    )
            except ValueError:
                raise ValidationError("Invalid Content-Length header", "content-length")

    async def _validate_content_type(self, request: Request) -> None:
        """验证Content-Type"""
        content_type = request.headers.get("content-type", "")

        # 如果有请求体，必须有正确的Content-Type
        if content_length and not content_type:
            raise ValidationError("Content-Type header required for requests with body", "content-type")

        # 验证Content-Type格式
        if content_type and not any(ct in content_type.lower() for ct in [
            "application/json",
            "multipart/form-data",
            "application/x-www-form-urlencoded"
        ]):
            raise ValidationError(f"Unsupported Content-Type: {content_type}", "content-type")

    def _create_validation_error_response(self, error: ValidationError) -> JSONResponse:
        """创建验证错误响应"""
        logger.warning(f"Request validation failed: {error.message}", extra={
            "field": error.field,
            "error_code": error.error_code
        })

        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ErrorResponse.create(
                message=error.message,
                error_type="invalid_request_error",
                param=error.field,
                code=error.error_code
            ).dict()
        )


def add_validation_middleware(app) -> None:
    """添加验证中间件到FastAPI应用"""
    app.add_middleware(ValidationMiddleware)
    logger.info("Request validation middleware configured")