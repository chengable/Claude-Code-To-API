"""
会话数据模型模块

定义会话管理相关的数据模型。
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
import uuid

from .message import ChatMessage


class Session(BaseModel):
    """会话数据模型"""
    session_id: str = Field(..., description="会话唯一标识符")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    last_activity: datetime = Field(default_factory=datetime.now, description="最后活动时间")
    claude_process_id: Optional[str] = Field(None, description="Claude进程ID")
    claude_session_id: Optional[str] = Field(None, description="Claude内部会话ID")
    message_count: int = Field(default=0, description="消息数量")
    is_active: bool = Field(True, description="会话是否活跃")

    # 会话配置
    claude_working_dir: Optional[str] = Field(None, description="Claude工作目录")
    max_message_history: int = Field(50, description="最大消息历史数量")
    timeout_minutes: int = Field(30, description="会话超时时间（分钟）")

    # 元数据
    user_agent: Optional[str] = Field(None, description="用户代理")
    client_ip: Optional[str] = Field(None, description="客户端IP地址")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="额外元数据")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

    def update_activity(self) -> None:
        """更新最后活动时间和消息计数"""
        self.last_activity = datetime.now()
        self.message_count += 1

    def is_expired(self) -> bool:
        """检查会话是否过期"""
        expiry_time = self.last_activity + timedelta(minutes=self.timeout_minutes)
        return datetime.now() > expiry_time

    def should_cleanup(self) -> bool:
        """检查会话是否应该被清理"""
        return not self.is_active or self.is_expired()

    def get_session_age(self) -> timedelta:
        """获取会话年龄"""
        return datetime.now() - self.created_at

    def get_idle_time(self) -> timedelta:
        """获取空闲时间"""
        return datetime.now() - self.last_activity

    def add_metadata(self, key: str, value: Any) -> None:
        """添加元数据"""
        self.metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """获取元数据"""
        return self.metadata.get(key, default)


class SessionCreateRequest(BaseModel):
    """创建会话请求"""
    session_id: Optional[str] = Field(None, description="会话ID，如果不提供则自动生成")
    claude_working_dir: Optional[str] = Field(None, description="Claude工作目录")
    max_message_history: int = Field(50, description="最大消息历史数量")
    timeout_minutes: int = Field(30, description="会话超时时间（分钟）")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="额外元数据")

    def create_session(self, **kwargs) -> Session:
        """创建会话实例"""
        session_id = self.session_id or f"session_{uuid.uuid4().hex[:12]}"

        return Session(
            session_id=session_id,
            claude_working_dir=self.claude_working_dir,
            max_message_history=self.max_message_history,
            timeout_minutes=self.timeout_minutes,
            metadata={**self.metadata, **kwargs}
        )


class SessionUpdateRequest(BaseModel):
    """更新会话请求"""
    is_active: Optional[bool] = Field(None, description="是否活跃")
    claude_session_id: Optional[str] = Field(None, description="Claude会话ID")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据更新")

    def apply_to_session(self, session: Session) -> None:
        """将更新应用到会话"""
        if self.is_active is not None:
            session.is_active = self.is_active

        if self.claude_session_id is not None:
            session.claude_session_id = self.claude_session_id

        if self.metadata is not None:
            session.metadata.update(self.metadata)


class SessionInfo(BaseModel):
    """会话信息响应"""
    session_id: str
    created_at: datetime
    last_activity: datetime
    message_count: int
    is_active: bool
    age_seconds: int = Field(description="会话年龄（秒）")
    idle_seconds: int = Field(description="空闲时间（秒）")
    is_expired: bool = Field(description="是否过期")
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_session(cls, session: Session) -> "SessionInfo":
        """从会话创建信息"""
        now = datetime.now()
        return cls(
            session_id=session.session_id,
            created_at=session.created_at,
            last_activity=session.last_activity,
            message_count=session.message_count,
            is_active=session.is_active,
            age_seconds=int((now - session.created_at).total_seconds()),
            idle_seconds=int((now - session.last_activity).total_seconds()),
            is_expired=session.is_expired(),
            metadata=session.metadata.copy()
        )


class SessionListResponse(BaseModel):
    """会话列表响应"""
    sessions: List[SessionInfo]
    total_count: int
    active_count: int
    expired_count: int

    @classmethod
    def create_from_sessions(cls, sessions: List[Session]) -> "SessionListResponse":
        """从会话列表创建响应"""
        session_infos = [SessionInfo.from_session(session) for session in sessions]

        active_count = sum(1 for info in session_infos if info.is_active and not info.is_expired)
        expired_count = sum(1 for info in session_infos if info.is_expired)

        return cls(
            sessions=session_infos,
            total_count=len(session_infos),
            active_count=active_count,
            expired_count=expired_count
        )