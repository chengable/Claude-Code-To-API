"""
CORS中间件模块

处理跨域资源共享。
"""

from typing import List
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

logger = logging.getLogger(__name__)


def add_cors_middleware(app: FastAPI) -> None:
    """添加CORS中间件到FastAPI应用"""

    # 允许的源
    allowed_origins: List[str] = [
        "http://localhost:3000",  # React开发服务器
        "http://localhost:8080",  # Vue开发服务器
        "http://localhost:8000",  # 其他开发服务器
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:8000",
    ]

    # 允许的方法
    allowed_methods: List[str] = [
        "GET",
        "POST",
        "PUT",
        "DELETE",
        "OPTIONS",
        "PATCH"
    ]

    # 允许的头部
    allowed_headers: List[str] = [
        "accept",
        "accept-language",
        "content-language",
        "content-type",
        "authorization",
        "x-requested-with",
        "openai-organization",
        "openai-project"
    ]

    # 暴露的头部
    expose_headers: List[str] = [
        "x-request-id",
        "x-ratelimit-limit",
        "x-ratelimit-remaining"
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=allowed_methods,
        allow_headers=allowed_headers,
        expose_headers=expose_headers,
        max_age=600,  # 预检请求缓存时间（秒）
    )

    logger.info("CORS middleware configured", extra={
        "allowed_origins": allowed_origins,
        "allowed_methods": allowed_methods,
        "allowed_headers": allowed_headers
    })