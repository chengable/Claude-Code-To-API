"""
API Key验证和频率限制服务

提供API Key验证、频率限制和使用统计功能。
"""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
import logging
from collections import defaultdict

from ..models.api_key import (
    APIKeyConfig, APIKeyUsage, APIKeyValidationError,
    RateLimitPeriod, OpenAIErrorResponse
)
from ..utils.config import config

logger = logging.getLogger(__name__)


class APIKeyService:
    """API Key验证和频率限制服务"""

    def __init__(self):
        # 存储API Key使用情况：key -> APIKeyUsage
        self._usage_storage: Dict[str, APIKeyUsage] = {}
        # 锁保护并发访问
        self._lock = asyncio.Lock()

    def _calculate_period_bounds(self, period: RateLimitPeriod) -> tuple[datetime, datetime]:
        """计算周期的开始和结束时间"""
        now = datetime.now(timezone.utc)

        if period == RateLimitPeriod.DAY:
            # 日周期：从今天的00:00:00 UTC到明天的00:00:00 UTC
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
        elif period == RateLimitPeriod.MONTH:
            # 月周期：从本月1日00:00:00 UTC到下月1日00:00:00 UTC
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            # 计算下个月的1日
            if now.month == 12:
                end = now.replace(year=now.year + 1, month=1, day=1,
                                hour=0, minute=0, second=0, microsecond=0)
            else:
                end = now.replace(month=now.month + 1, day=1,
                                hour=0, minute=0, second=0, microsecond=0)
        else:
            raise ValueError(f"Unsupported period: {period}")

        return start, end

    async def _get_or_create_usage(self, api_key_config: APIKeyConfig) -> APIKeyUsage:
        """获取或创建API Key使用记录"""
        async with self._lock:
            key = api_key_config.key

            if key not in self._usage_storage:
                # 创建新的使用记录
                period_start, period_end = self._calculate_period_bounds(api_key_config.period)
                usage = APIKeyUsage(
                    api_key=key,
                    current_period_requests=0,
                    period_start=period_start,
                    period_end=period_end
                )
                self._usage_storage[key] = usage
            else:
                usage = self._usage_storage[key]

                # 检查周期是否已过期
                if usage.is_period_expired():
                    logger.info(f"API Key {key[:8]}... 的使用周期已过期，重置计数")
                    period_start, period_end = self._calculate_period_bounds(api_key_config.period)
                    usage.reset_period(period_start, period_end)

            return usage

    async def validate_api_key(self, api_key: str) -> tuple[bool, Optional[OpenAIErrorResponse]]:
        """
        验证API Key并检查频率限制

        Args:
            api_key: 要验证的API Key

        Returns:
            tuple: (是否有效, 错误响应)
        """
        try:
            # 检查是否启用API Key验证
            if not config.api_key_enabled:
                return True, None

            # 获取API Key配置
            api_key_config = config.get_api_key_config(api_key)
            if not api_key_config:
                logger.warning(f"无效的API Key: {api_key[:8] if len(api_key) > 8 else api_key}...")
                return False, OpenAIErrorResponse.from_validation_error(
                    APIKeyValidationError.invalid_key()
                )

            # 获取使用记录
            usage = await self._get_or_create_usage(api_key_config)

            # 检查频率限制
            if not usage.can_make_request(api_key_config.max_requests):
                logger.warning(f"API Key {api_key[:8]}... 已达到频率限制: "
                             f"{usage.current_period_requests}/{api_key_config.max_requests} "
                             f"({api_key_config.period})")

                # 计算重试时间（秒）
                now = datetime.now(timezone.utc)
                retry_after_seconds = int((usage.period_end - now).total_seconds())

                return False, OpenAIErrorResponse.from_validation_error(
                    APIKeyValidationError.rate_limit_exceeded(retry_after_seconds)
                )

            # 记录这次请求
            usage.record_request()

            logger.debug(f"API Key {api_key[:8]}... 验证成功，"
                        f"当前周期使用: {usage.current_period_requests}/{api_key_config.max_requests}")

            return True, None

        except Exception as e:
            logger.error(f"API Key验证过程中发生错误: {e}")
            import traceback
            logger.error(f"错误详情: {traceback.format_exc()}")
            return False, OpenAIErrorResponse.from_validation_error(
                APIKeyValidationError.invalid_key()
            )

    async def get_usage_stats(self, api_key: str) -> Optional[Dict[str, Any]]:
        """
        获取API Key使用统计

        Args:
            api_key: API Key

        Returns:
            使用统计信息，如果Key不存在则返回None
        """
        if not config.api_key_enabled:
            return None

        api_key_config = config.get_api_key_config(api_key)
        if not api_key_config:
            return None

        usage = await self._get_or_create_usage(api_key_config)

        return {
            "api_key": api_key[:8] + "...",  # 只显示前8位
            "current_period_requests": usage.current_period_requests,
            "max_requests": api_key_config.max_requests,
            "period": api_key_config.period,
            "period_start": usage.period_start.isoformat(),
            "period_end": usage.period_end.isoformat(),
            "last_used": usage.last_used.isoformat() if usage.last_used else None,
            "remaining_requests": api_key_config.max_requests - usage.current_period_requests
        }

    async def reset_usage(self, api_key: str) -> bool:
        """
        重置API Key使用记录（仅用于管理目的）

        Args:
            api_key: 要重置的API Key

        Returns:
            是否成功重置
        """
        async with self._lock:
            if api_key in self._usage_storage:
                del self._usage_storage[api_key]
                logger.info(f"已重置API Key {api_key[:8]}... 的使用记录")
                return True
            return False

    def get_all_stats(self) -> Dict[str, Any]:
        """获取所有API Key的统计信息（用于监控）"""
        stats = {
            "total_keys": len(config.api_keys),
            "enabled": config.api_key_enabled,
            "active_keys": len(self._usage_storage),
            "keys": []
        }

        for key_config in config.api_keys:
            key_stats = {
                "key": key_config.key[:8] + "...",
                "description": key_config.description,
                "max_requests": key_config.max_requests,
                "period": key_config.period
            }

            if key_config.key in self._usage_storage:
                usage = self._usage_storage[key_config.key]
                key_stats.update({
                    "current_usage": usage.current_period_requests,
                    "remaining": key_config.max_requests - usage.current_period_requests,
                    "last_used": usage.last_used.isoformat() if usage.last_used else None,
                    "period_start": usage.period_start.isoformat(),
                    "period_end": usage.period_end.isoformat()
                })

            stats["keys"].append(key_stats)

        return stats


# 创建全局API Key服务实例
api_key_service = APIKeyService()