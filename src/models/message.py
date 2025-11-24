"""
消息模型模块

定义OpenAI格式的请求和响应消息模型。
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator
from enum import Enum

from .response import MessageRole, Usage


class ContentType(str, Enum):
    """内容类型枚举"""
    TEXT = "text"
    IMAGE_URL = "image_url"


class ContentPart(BaseModel):
    """多模态内容部分"""
    type: ContentType
    text: Optional[str] = None
    image_url: Optional[Dict[str, str]] = None

    @field_validator('image_url')
    @classmethod
    def validate_image_url(cls, v, info):
        if v is not None and info.data.get('type') == ContentType.IMAGE_URL:
            if 'url' not in v:
                raise ValueError("image_url must contain 'url' field")
        return v


class ChatMessage(BaseModel):
    """聊天消息模型"""
    role: MessageRole
    content: Union[str, List[ContentPart]]
    name: Optional[str] = None
    # OpenAI支持但非必需的字段
    function_call: Optional[Dict[str, Any]] = None

    @field_validator('content')
    @classmethod
    def validate_content(cls, v, info):
        role = info.data.get('role') if info.data else None

        # 系统消息不能为空
        if role == MessageRole.SYSTEM and (not v or (isinstance(v, list) and not v)):
            raise ValueError("System message content cannot be empty")

        # 用户消息不能为空
        if role == MessageRole.USER and (not v or (isinstance(v, list) and not v)):
            raise ValueError("User message content cannot be empty")

        return v

    @classmethod
    def create_user_message(cls, content: str, name: Optional[str] = None) -> "ChatMessage":
        """创建用户消息"""
        return cls(role=MessageRole.USER, content=content, name=name)

    @classmethod
    def create_system_message(cls, content: str) -> "ChatMessage":
        """创建系统消息"""
        return cls(role=MessageRole.SYSTEM, content=content)

    @classmethod
    def create_assistant_message(cls, content: str) -> "ChatMessage":
        """创建助手消息"""
        return cls(role=MessageRole.ASSISTANT, content=content)

    def get_text_content(self) -> str:
        """获取文本内容"""
        if isinstance(self.content, str):
            return self.content
        elif isinstance(self.content, list):
            text_parts = []
            for part in self.content:
                if part.type == ContentType.TEXT and part.text:
                    text_parts.append(part.text)
            return "\n".join(text_parts)
        return ""

    def to_claude_format(self) -> str:
        """转换为Claude命令行格式"""
        return self.get_text_content()


class ChatCompletionRequest(BaseModel):
    """聊天完成请求模型"""
    model: str = Field(..., description="模型ID")
    messages: List[ChatMessage] = Field(..., min_items=1, description="对话消息列表")
    max_tokens: Optional[int] = Field(1000, ge=1, le=4096, description="最大生成token数")
    temperature: Optional[float] = Field(1.0, ge=0.0, le=2.0, description="采样温度")
    top_p: Optional[float] = Field(1.0, ge=0.0, le=1.0, description="核采样参数")
    stream: Optional[bool] = Field(False, description="是否流式响应")
    stop: Optional[Union[str, List[str]]] = Field(None, description="停止序列")
    user: Optional[str] = Field(None, pattern="^[a-zA-Z0-9_-]+$", max_length=255, description="用户标识符")

    class Config:
        json_schema_extra = {
            "example": {
                "model": "claude-3-sonnet-20240229",
                "messages": [
                    {
                        "role": "user",
                        "content": "Hello, how are you?"
                    }
                ],
                "max_tokens": 1000,
                "temperature": 1.0,
                "stream": False
            }
        }

    @field_validator('messages')
    @classmethod
    def validate_messages(cls, v):
        if not v:
            raise ValueError("Messages list cannot be empty")

        # 验证消息顺序
        for i, message in enumerate(v):
            # 系统消息只能在开头
            if message.role == MessageRole.SYSTEM and i > 0:
                raise ValueError("System messages must be at the beginning")

            # 不能连续两个助手消息（用户消息可以连续）
            if i > 0 and message.role == MessageRole.ASSISTANT:
                prev_role = v[i-1].role
                if prev_role == MessageRole.ASSISTANT:
                    raise ValueError("Consecutive assistant messages are not allowed")

        return v

    @field_validator('stop')
    @classmethod
    def validate_stop(cls, v):
        if isinstance(v, list) and len(v) > 4:
            raise ValueError("Maximum 4 stop sequences allowed")
        return v

    def get_session_id(self) -> Optional[str]:
        """获取会话ID"""
        return self.user

    def get_last_user_message(self) -> Optional[ChatMessage]:
        """获取最后一条用户消息"""
        for message in reversed(self.messages):
            if message.role == MessageRole.USER:
                return message
        return None

    def get_system_message(self) -> Optional[ChatMessage]:
        """获取系统消息"""
        if self.messages and self.messages[0].role == MessageRole.SYSTEM:
            return self.messages[0]
        return None

    def get_conversation_history(self) -> List[ChatMessage]:
        """获取对话历史（排除系统消息）"""
        if self.messages and self.messages[0].role == MessageRole.SYSTEM:
            return self.messages[1:]
        return self.messages

    def to_claude_prompt(self) -> str:
        """转换为Claude命令行提示格式，包含完整的对话上下文"""
        # 构建完整的对话上下文
        prompt_parts = []
        
        # 添加系统消息（如果有）
        system_msg = self.get_system_message()
        if system_msg:
            prompt_parts.append(f"System: {system_msg.get_text_content()}")
        
        # 添加对话历史
        conversation_history = self.get_conversation_history()
        for message in conversation_history:
            role_name = "Human" if message.role == MessageRole.USER else "Assistant"
            content = message.get_text_content()
            prompt_parts.append(f"{role_name}: {content}")
        
        # 组合成完整的提示
        if prompt_parts:
            # 确保最后一条是用户消息，如果不是则添加提示
            if conversation_history and conversation_history[-1].role != MessageRole.USER:
                prompt_parts.append("Human: ")
            
            result = "\n\n".join(prompt_parts)
            print(f"🔍 to_claude_prompt生成的多轮对话内容: {repr(result[:200])}{'...' if len(result) > 200 else ''}")
            return result
        
        # 如果没有任何消息，返回空字符串
        print("⚠️ 没有找到任何消息")
        return ""


class ModelInfo(BaseModel):
    """模型信息"""
    id: str
    object: str = "model"
    created: int
    owned_by: str

    class Config:
        json_schema_extra = {
            "example": {
                "id": "claude-3-sonnet-20240229",
                "object": "model",
                "created": 1677610602,
                "owned_by": "anthropic"
            }
        }


class ModelsListRequest(BaseModel):
    """模型列表请求（通常为空）"""
    pass


class ModelUsage(BaseModel):
    """模型使用信息"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def add(self, other: "ModelUsage") -> "ModelUsage":
        """合并使用信息"""
        return ModelUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens
        )