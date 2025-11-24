"""
健康检查路由模块

提供健康检查和系统状态监控端点。
"""

from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter, HTTPException
import logging

from ...models.response import HealthResponse
from ...services.session_manager import get_session_manager
from ...services.claude_service import get_claude_service
from ...utils.config import config

logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(tags=["health"])


@router.get("/")
async def health_check() -> HealthResponse:
    """
    基础健康检查

    返回服务和系统的基础状态信息。
    """
    try:
        session_manager = get_session_manager()
        claude_service = get_claude_service()

        # 检查Claude CLI可用性
        claude_available = config.validate_claude_setup()

        # 获取系统状态
        active_sessions = session_manager.get_active_session_count()
        total_sessions = session_manager.get_session_count()
        active_processes = claude_service.get_active_process_count()

        return HealthResponse(
            status="healthy" if claude_available else "degraded",
            timestamp=datetime.now().isoformat(),
            version="1.0.0",
            active_sessions=active_sessions
        )

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail={
            "status": "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        })


@router.get("/detailed")
async def detailed_health_check() -> Dict[str, Any]:
    """
    详细健康检查

    返回详细的系统和组件状态信息。
    """
    try:
        session_manager = get_session_manager()
        claude_service = get_claude_service()

        # Claude CLI状态
        claude_status = {
            "available": config.validate_claude_setup(),
            "command": config.claude_command,
            "working_dir": str(config.claude_working_path) if config.claude_working_path else None
        }

        # 会话统计
        session_stats = session_manager.get_stats()
        active_sessions = await session_manager.get_active_sessions()

        session_status = {
            "total_active": len(active_sessions),
            "total_registered": session_manager.get_session_count(),
            "stats": session_stats,
            "oldest_session": None,
            "newest_session": None
        }

        if active_sessions:
            oldest = min(active_sessions, key=lambda s: s.created_at)
            newest = max(active_sessions, key=lambda s: s.created_at)
            session_status["oldest_session"] = {
                "id": oldest.session_id,
                "created_at": oldest.created_at.isoformat(),
                "age_seconds": oldest.get_session_age().total_seconds()
            }
            session_status["newest_session"] = {
                "id": newest.session_id,
                "created_at": newest.created_at.isoformat(),
                "age_seconds": newest.get_session_age().total_seconds()
            }

        # Claude进程状态
        process_status = {
            "active_processes": claude_service.get_active_process_count(),
            "process_ids": list(claude_service.active_processes.keys())
        }

        # 系统配置
        config_status = {
            "host": config.host,
            "port": config.port,
            "debug": config.debug,
            "log_level": config.log_level,
            "session_timeout": config.session_timeout,
            "max_concurrent_sessions": config.max_concurrent_sessions,
            "claude_timeout": config.claude_timeout,
            "request_timeout": config.request_timeout,
            "max_request_size": config.max_request_size
        }

        # 计算总体健康状态
        components_healthy = [
            claude_status["available"],
            True,  # Session manager always healthy if running
            True   # Claude service always healthy if running
        ]

        overall_status = "healthy" if all(components_healthy) else "degraded"

        return {
            "status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0",
            "components": {
                "claude_cli": claude_status,
                "session_manager": session_status,
                "claude_service": process_status,
                "configuration": config_status
            },
            "uptime": None,  # TODO: 实现应用运行时间统计
            "system_info": {
                "python_version": "3.12.x",  # TODO: 动态获取
                "platform": None  # TODO: 动态获取平台信息
            }
        }

    except Exception as e:
        logger.error(f"Detailed health check failed: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
            "components": {}
        }


@router.get("/ready")
async def readiness_check() -> Dict[str, Any]:
    """
    就绪检查

    检查服务是否准备好接收请求。
    """
    try:
        # 检查关键组件
        session_manager = get_session_manager()
        claude_service = get_claude_service()

        claude_ready = config.validate_claude_setup()
        sessions_ready = session_manager.get_session_count() >= 0  # 基本检查
        processes_ready = True  # Claude service总是就绪的

        ready = claude_ready and sessions_ready and processes_ready

        return {
            "ready": ready,
            "timestamp": datetime.now().isoformat(),
            "checks": {
                "claude_cli": "ok" if claude_ready else "failed",
                "session_manager": "ok" if sessions_ready else "failed",
                "claude_service": "ok" if processes_ready else "failed"
            }
        }

    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return {
            "ready": False,
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }


@router.get("/live")
async def liveness_check() -> Dict[str, Any]:
    """
    存活检查

    简单的存活检查，用于确定服务是否在运行。
    """
    return {
        "alive": True,
        "timestamp": datetime.now().isoformat(),
        "pid": None  # TODO: 获取进程ID
    }


# 导出路由器
__all__ = ["router"]