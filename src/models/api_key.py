"""
API Key数据模型

定义API Key相关的数据结构和验证逻辑。
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, validator


class RateLimitPeriod(str, Enum):
    """频率限制周期枚举"""
    DAY = "day"
    MONTH = "month"


class APIKeyConfig(BaseModel):
    """API Key配置模型"""
    key: str = Field(..., description="API密钥")
    max_requests: int = Field(..., gt=0, description="最大请求次数")
    period: RateLimitPeriod = Field(..., description="限制周期")
    description: Optional[str] = Field(None, description="API Key描述")

    @validator('key')
    def validate_key_format(cls, v):
        """验证API Key格式"""
        if not v or len(v) < 8:
            raise ValueError("API Key长度不能少于8个字符")
        return v


class APIKeyUsage(BaseModel):
    """API Key使用记录"""
    api_key: str
    current_period_requests: int = 0
    period_start: datetime
    period_end: datetime
    last_used: Optional[datetime] = None

    def is_period_expired(self) -> bool:
        """检查当前周期是否已过期"""
        now = datetime.now(timezone.utc)
        return now > self.period_end

    def can_make_request(self, max_requests: int) -> bool:
        """检查是否可以发起请求"""
        return self.current_period_requests < max_requests

    def record_request(self) -> None:
        """记录一次请求"""
        self.current_period_requests += 1
        self.last_used = datetime.now(timezone.utc)

    def reset_period(self, new_start: datetime, new_end: datetime) -> None:
        """重置周期"""
        self.current_period_requests = 0
        self.period_start = new_start
        self.period_end = new_end


class APIKeyValidationError(BaseModel):
    """API Key验证错误响应"""
    error: Dict[str, Any]

    @classmethod
    def invalid_key(cls) -> "APIKeyValidationError":
        """无效Key错误"""
        return cls(
            error={
                "message": "Invalid API key provided",
                "type": "invalid_api_key",
                "code": "invalid_api_key"
            }
        )

    @classmethod
    def rate_limit_exceeded(cls, retry_after: Optional[int] = None) -> "APIKeyValidationError":
        """频率限制超出错误"""
        error_data = {
            "message": "Rate limit exceeded for this API key",
            "type": "rate_limit_exceeded",
            "code": "rate_limit_exceeded"
        }
        if retry_after:
            error_data["retry_after"] = retry_after
        return cls(error=error_data)


# OpenAI兼容的错误响应格式
class OpenAIErrorResponse(BaseModel):
    """OpenAI格式的错误响应"""
    error: Dict[str, Any]

    @classmethod
    def from_validation_error(cls, validation_error: APIKeyValidationError) -> "OpenAIErrorResponse":
        """从验证错误创建OpenAI格式响应"""
        return cls(error=validation_error.error)