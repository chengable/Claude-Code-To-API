"""
FastAPI应用主入口

创建并配置FastAPI应用实例。
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from ..utils.config import Config
from ..utils.exceptions import setup_exception_handlers
from .middleware.cors import add_cors_middleware

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    logger.info("Claude OpenAI API Wrapper starting up...")

    # 启动会话管理器
    from ..services.session_manager import start_session_manager
    await start_session_manager()

    # 验证Claude CLI是否可用
    from ..utils.config import config
    if not config.validate_claude_setup():
        logger.warning("Claude CLI validation failed - some features may not work")

    logger.info("Claude OpenAI API Wrapper startup completed")

    yield

    # 关闭时执行
    logger.info("Claude OpenAI API Wrapper shutting down...")

    # 优雅关闭处理
    try:
        # 停止会话管理器
        from ..services.session_manager import stop_session_manager
        await stop_session_manager()

        # 清理Claude进程
        from ..services.claude_service import get_claude_service
        claude_service = get_claude_service()
        await claude_service.cleanup_all_processes()

        logger.info("Graceful shutdown completed")
    except Exception as e:
        logger.error(f"Error during graceful shutdown: {e}")
    finally:
        logger.info("Claude OpenAI API Wrapper shutdown complete")


def create_app() -> FastAPI:
    """创建FastAPI应用实例"""

    # 创建FastAPI应用
    app = FastAPI(
        title="Claude OpenAI API Wrapper",
        description="完全兼容OpenAI格式的Claude API封装服务",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json"
    )

    # 添加CORS中间件
    add_cors_middleware(app)

    # 添加API Key验证中间件
    from .middleware.api_key_auth import APIKeyAuthMiddleware
    app.add_middleware(APIKeyAuthMiddleware)

    # 添加请求响应日志中间件（调试用）
    from .middleware.request_logging import add_request_logging_middleware
    add_request_logging_middleware(app)

    # 添加验证中间件 (暂时禁用以测试核心功能)
    # from .middleware.validation import add_validation_middleware
    # add_validation_middleware(app)

    # 添加异常处理器
    setup_exception_handlers(app)

    # 添加路由
    from .routes.chat import router as chat_router
    app.include_router(chat_router, prefix="/v1")

    # 添加API Key统计路由
    from .routes.api_key_stats import router as api_key_stats_router
    app.include_router(api_key_stats_router, prefix="/v1")

    # 添加健康检查路由
    from .routes.health import router as health_router
    app.include_router(health_router, prefix="/v1")

    return app


# 创建全局应用实例
app = create_app()


if __name__ == "__main__":
    import uvicorn

    config = Config()

    uvicorn.run(
        "src.api.main:app",
        host=config.host,
        port=config.port,
        reload=config.debug,
        log_level=config.log_level.lower()
    )