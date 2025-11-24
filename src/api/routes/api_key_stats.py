"""
API Key统计和管理路由

提供API Key使用情况查询和统计功能。
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, Optional
import logging

from ...services.api_key_service import api_key_service
from ...utils.config import config
from ...models.api_key import OpenAIErrorResponse
from ..middleware.api_key_auth import api_key_dependency

logger = logging.getLogger(__name__)

router = APIRouter(tags=["API Key管理"])


@router.get("/api-key/stats", summary="获取API Key使用统计")
async def get_api_key_stats(
    api_key: Optional[str] = Depends(api_key_dependency.verify_api_key)
) -> Dict[str, Any]:
    """
    获取当前API Key的使用统计信息

    需要有效的API Key才能访问
    """
    if not config.api_key_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API Key功能未启用"
        )

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key required"
        )

    try:
        stats = await api_key_service.get_usage_stats(api_key)
        if stats is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API Key not found"
            )

        return stats

    except Exception as e:
        logger.error(f"获取API Key统计失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/api-key/admin/stats", summary="获取所有API Key统计信息")
async def get_all_api_key_stats(
    api_key: Optional[str] = Depends(api_key_dependency.verify_api_key)
) -> Dict[str, Any]:
    """
    获取所有API Key的统计信息（管理功能）

    注意：这是一个管理端点，未来可能需要特殊的权限
    """
    if not config.api_key_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API Key功能未启用"
        )

    try:
        return api_key_service.get_all_stats()

    except Exception as e:
        logger.error(f"获取所有API Key统计失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/api-key/admin/reset", summary="重置API Key使用记录")
async def reset_api_key_usage(
    api_key_to_reset: str,
    api_key: Optional[str] = Depends(api_key_dependency.verify_api_key)
) -> Dict[str, Any]:
    """
    重置指定API Key的使用记录（管理功能）

    注意：这是一个管理端点，未来可能需要特殊的权限
    """
    if not config.api_key_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API Key功能未启用"
        )

    try:
        success = await api_key_service.reset_usage(api_key_to_reset)

        return {
            "success": success,
            "message": "API Key使用记录已重置" if success else "API Key不存在或无需重置"
        }

    except Exception as e:
        logger.error(f"重置API Key使用记录失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )