"""
API响应模型模块

定义OpenAI兼容的响应格式。
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
from enum import Enum


class FinishReason(str, Enum):
    """完成原因枚举"""
    STOP = "stop"
    LENGTH = "length"
    CONTENT_FILTER = "content_filter"
    FUNCTION_CALL = "function_call"


class MessageRole(str, Enum):
    """消息角色枚举"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class Message(BaseModel):
    """消息模型"""
    role: MessageRole
    content: str
    name: Optional[str] = None


class Usage(BaseModel):
    """令牌使用信息"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class Delta(BaseModel):
    """流式响应增量"""
    role: Optional[MessageRole] = None
    content: Optional[str] = None


class Choice(BaseModel):
    """选择项模型"""
    index: int
    message: Optional[Message] = None
    delta: Optional[Delta] = None
    finish_reason: Optional[FinishReason] = None


class BaseResponse(BaseModel):
    """基础响应模型"""
    id: str
    object: str
    created: int = Field(default_factory=lambda: int(datetime.now().timestamp()))
    model: str = "claude-3-sonnet-20240229"


class ChatCompletionResponse(BaseResponse):
    """聊天完成响应模型"""
    object: str = "chat.completion"
    choices: List[Choice]
    usage: Optional[Usage] = None
    system_fingerprint: Optional[str] = None

    @classmethod
    def create(
        cls,
        response_id: str,
        message_content: str,
        model: str = "claude-3-sonnet-20240229",
        finish_reason: FinishReason = FinishReason.STOP,
        usage: Optional[Usage] = None
    ) -> "ChatCompletionResponse":
        """创建聊天完成响应"""
        return cls(
            id=response_id,
            model=model,
            choices=[
                Choice(
                    index=0,
                    message=Message(
                        role=MessageRole.ASSISTANT,
                        content=message_content
                    ),
                    finish_reason=finish_reason
                )
            ],
            usage=usage
        )


class ChatCompletionStreamResponse(BaseResponse):
    """聊天完成流式响应模型"""
    object: str = "chat.completion.chunk"
    choices: List[Choice]

    @classmethod
    def create(
        cls,
        response_id: str,
        delta_content: Optional[str] = None,
        delta_role: Optional[MessageRole] = None,
        model: str = "claude-3-sonnet-20240229",
        finish_reason: Optional[FinishReason] = None
    ) -> "ChatCompletionStreamResponse":
        """创建流式响应"""
        delta = Delta()
        if delta_role:
            delta.role = delta_role
        # 修改：当传入空字符串时也保留content字段，避免出现null
        if delta_content is not None:
            delta.content = delta_content

        return cls(
            id=response_id,
            model=model,
            choices=[
                Choice(
                    index=0,
                    delta=delta,
                    finish_reason=finish_reason
                )
            ]
        )


class ErrorDetail(BaseModel):
    """错误详情"""
    message: str
    type: str
    param: Optional[str] = None
    code: Optional[str] = None


class ErrorResponse(BaseModel):
    """错误响应模型"""
    error: ErrorDetail
    object: str = "error"

    @classmethod
    def create(
        cls,
        message: str,
        error_type: str = "invalid_request_error",
        param: Optional[str] = None,
        code: Optional[str] = None
    ) -> "ErrorResponse":
        """创建错误响应"""
        return cls(
            error=ErrorDetail(
                message=message,
                type=error_type,
                param=param,
                code=code
            )
        )


class ModelInfo(BaseModel):
    """模型信息"""
    id: str
    object: str = "model"
    created: int
    owned_by: str


class ModelsResponse(BaseModel):
    """模型列表响应"""
    object: str = "list"
    data: List[ModelInfo]

    @classmethod
    def create_default(cls) -> "ModelsResponse":
        """创建默认模型列表"""
        return cls(
            data=[
                ModelInfo(
                    id="gpt-5",
                    created=1677610602,
                    owned_by="openai"
                ),
                ModelInfo(
                    id="GLM-4.6",
                    created=1677610602,
                    owned_by="zhipu"
                )
            ]
        )


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = "healthy"
    timestamp: str
    version: str = "1.0.0"
    active_sessions: int = 0