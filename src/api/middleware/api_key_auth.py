"""
API Key验证中间件

在API请求处理之前验证API Key并进行频率限制检查。
"""

import json
from typing import Optional
from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import logging

from ...services.api_key_service import api_key_service
from ...utils.config import config
from ...models.api_key import OpenAIErrorResponse

logger = logging.getLogger(__name__)

# HTTP Bearer认证方案
security = HTTPBearer(auto_error=False)


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """API Key验证中间件"""

    # 不需要验证的路径
    EXCLUDED_PATHS = {
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/favicon.ico",
        "/",
        "/v1/models",
        "/models",
    }

    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        """中间件处理逻辑"""
        path = request.url.path

        # 检查是否为排除路径
        if path in self.EXCLUDED_PATHS or path.startswith("/static"):
            return await call_next(request)

        # 如果未启用API Key验证，直接通过
        if not config.api_key_enabled:
            return await call_next(request)

        try:
            # 提取API Key
            api_key = await self._extract_api_key(request)

            if api_key is None:
                return self._create_error_response(
                    message="API Key required",
                    error_type="missing_api_key",
                    status_code=status.HTTP_401_UNAUTHORIZED
                )

            # 验证API Key
            is_valid, error_response = await api_key_service.validate_api_key(api_key)

            if not is_valid:
                return self._create_openai_error_response(error_response)

            # 将API Key信息添加到请求状态中
            request.state.api_key = api_key

            return await call_next(request)

        except Exception as e:
            logger.error(f"API Key验证过程中发生错误: {e}")
            return self._create_error_response(
                message="Internal server error during API key validation",
                error_type="internal_error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    async def _extract_api_key(self, request: Request) -> Optional[str]:
        """从请求中提取API Key"""
        # 1. 首先尝试从Authorization header中获取
        authorization: str = request.headers.get("Authorization")
        if authorization:
            try:
                scheme, credentials = authorization.split(" ", 1)
                if scheme.lower() == "bearer":
                    return credentials
            except ValueError:
                # Header格式不正确
                pass

        # 2. 尝试从查询参数中获取 (OpenAI格式)
        api_key = request.query_params.get("api_key")
        if api_key:
            return api_key

        # 3. 尝试从请求体中获取 (仅对POST/PUT请求)
        if request.method in ("POST", "PUT", "PATCH"):
            try:
                # 读取请求体
                body = await request.body()
                if body:
                    body_data = json.loads(body.decode("utf-8"))
                    if "api_key" in body_data:
                        return body_data["api_key"]
            except (json.JSONDecodeError, UnicodeDecodeError):
                # 无法解析请求体，忽略
                pass

        return None

    def _create_error_response(
        self,
        message: str,
        error_type: str,
        status_code: int = status.HTTP_401_UNAUTHORIZED
    ) -> JSONResponse:
        """创建标准错误响应"""
        error_response = {
            "error": {
                "message": message,
                "type": error_type,
                "code": error_type
            }
        }

        return JSONResponse(
            content=error_response,
            status_code=status_code,
            headers={"Content-Type": "application/json"}
        )

    def _create_openai_error_response(
        self,
        openai_error: OpenAIErrorResponse,
        status_code: int = status.HTTP_401_UNAUTHORIZED
    ) -> JSONResponse:
        """创建OpenAI格式的错误响应"""
        return JSONResponse(
            content=openai_error.model_dump(),
            status_code=status_code,
            headers={"Content-Type": "application/json"}
        )


class APIKeyDependency:
    """API Key依赖注入"""

    @staticmethod
    async def verify_api_key(request: Request) -> Optional[str]:
        """验证API Key的依赖函数"""
        if not config.api_key_enabled:
            return None

        # 从中间件设置的状态中获取API Key
        api_key = getattr(request.state, "api_key", None)
        if api_key is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API Key required"
            )

        return api_key


# 创建依赖实例
api_key_dependency = APIKeyDependency()