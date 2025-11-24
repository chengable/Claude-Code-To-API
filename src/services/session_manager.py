"""
会话管理服务模块

处理客户端会话的创建、管理、清理和上下文保持。
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
import logging
from collections import defaultdict
import weakref

from ..models.session import Session, SessionCreateRequest, SessionUpdateRequest
from ..models.message import ChatMessage
from ..utils.config import config
from ..utils.exceptions import SessionError
from .database import get_database_manager, DatabaseManager

logger = logging.getLogger(__name__)


class SessionManager:
    """会话管理器"""

    def __init__(self):
        self.sessions: Dict[str, Session] = {}
        self.cleanup_task: Optional[asyncio.Task] = None
        self._session_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self.db_manager: DatabaseManager = get_database_manager()
        self.stats = {
            'total_sessions_created': 0,
            'total_sessions_cleaned': 0,
            'cleanup_runs': 0
        }

    async def start(self) -> None:
        """启动会话管理器"""
        # 初始化数据库
        await self.db_manager.initialize()
        
        # 启动清理任务
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Session manager started with database support")

    async def stop(self) -> None:
        """停止会话管理器"""
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass

        # 清理所有会话
        await self.cleanup_all_sessions()
        
        # 关闭数据库连接
        await self.db_manager.close()
        
        logger.info("Session manager stopped")

    async def create_session(self, request: SessionCreateRequest, **kwargs) -> Session:
        """创建新会话"""
        async with self._session_locks["create"]:
            # 检查会话ID是否已存在
            if request.session_id and request.session_id in self.sessions:
                existing_session = self.sessions[request.session_id]
                if existing_session.is_active:
                    raise SessionError(f"Session '{request.session_id}' already exists", request.session_id)

            session = request.create_session(**kwargs)
            # 使用实际创建的session的session_id
            session_id = session.session_id
            self.sessions[session_id] = session

            # 保存到数据库
            session_data = {
                'session_id': session_id,
                'claude_session_id': session.claude_session_id,
                'claude_working_dir': str(session.claude_working_dir),
                'created_at': session.created_at,
                'last_activity': session.last_activity,
                'timeout_minutes': session.timeout_minutes,
                'is_active': session.is_active
            }
            await self.db_manager.create_session(session_data)

            self.stats['total_sessions_created'] += 1

            logger.info(f"Session created and saved to database", extra={
                'session_id': session_id,
                'created_at': session.created_at.isoformat(),
                'timeout_minutes': session.timeout_minutes
            })

            return session

    async def get_session(self, session_id: str) -> Optional[Session]:
        """获取会话"""
        if session_id not in self.sessions:
            return None

        session = self.sessions[session_id]

        # 检查会话是否过期
        if session.is_expired():
            logger.info(f"Session expired during retrieval", extra={
                'session_id': session_id,
                'last_activity': session.last_activity.isoformat()
            })
            await self.remove_session(session_id)
            return None

        return session

    async def update_session(self, session_id: str, request: SessionUpdateRequest) -> Optional[Session]:
        """更新会话"""
        async with self._session_locks[session_id]:
            session = await self.get_session(session_id)
            if not session:
                raise SessionError(f"Session '{session_id}' not found", session_id)

            request.apply_to_session(session)
            session.update_activity()

            # 同步更新到数据库
            update_data = {}
            if request.claude_session_id is not None:
                update_data['claude_session_id'] = request.claude_session_id
            if request.is_active is not None:
                update_data['is_active'] = request.is_active
            if request.metadata is not None:
                update_data['metadata'] = json.dumps(request.metadata)
            
            # 总是更新最后活动时间
            update_data['last_activity'] = session.last_activity.isoformat()
            
            await self.db_manager.update_session(session_id, update_data)

            logger.debug(f"Session updated in memory and database", extra={
                'session_id': session_id,
                'updates': request.dict(exclude_unset=True)
            })

            return session

    async def remove_session(self, session_id: str) -> bool:
        """移除会话"""
        if session_id not in self.sessions:
            # 检查数据库中是否存在
            db_session = await self.db_manager.get_session(session_id)
            if not db_session:
                return False

        # 从内存中移除
        session = self.sessions.pop(session_id, None)
        if session:
            session.is_active = False

        # 从数据库中删除
        await self.db_manager.delete_session(session_id)

        logger.info(f"Session removed from memory and database", extra={
            'session_id': session_id,
            'existed_duration': session.get_session_age().total_seconds() if session else 0
        })

        return True

    async def get_or_create_session(
        self,
        session_id: Optional[str] = None,
        **kwargs
    ) -> Session:
        """获取或创建会话"""
        logger.debug(f"get_or_create_session called with session_id: {session_id}")
        logger.debug(f"Current sessions in memory: {list(self.sessions.keys())}")
        
        if session_id:
            # 首先从内存中查找
            session = await self.get_session(session_id)
            logger.debug(f"get_session returned: {session}")
            if session:
                session.update_activity()
                logger.info(f"Using existing session from memory: {session_id}")
                return session
            
            # 从数据库中查找
            db_session = await self.db_manager.get_session(session_id)
            if db_session:
                logger.info(f"Found session in database: {session_id}")
                # 重新创建Session对象并加载到内存
                request = SessionCreateRequest(
                    session_id=session_id,
                    claude_working_dir=db_session.get('claude_working_dir', kwargs.get('claude_working_dir')),
                    **kwargs
                )
                session = request.create_session()
                session.claude_session_id = db_session.get('claude_session_id')
                session.last_activity = datetime.fromisoformat(db_session['last_activity'])
                self.sessions[session_id] = session
                session.update_activity()
                
                # 更新数据库中的最后活动时间
                await self.db_manager.update_session(session_id, {
                    'last_activity': session.last_activity.isoformat()
                })
                
                logger.info(f"Restored session from database: {session_id}")
                return session
            else:
                logger.warning(f"Session not found in memory or database: {session_id}")

        # 创建新会话
        logger.info(f"Creating new session with session_id: {session_id}")
        request = SessionCreateRequest(session_id=session_id, **kwargs)
        return await self.create_session(request)

    async def add_message_to_session(
        self,
        session_id: str,
        message: ChatMessage,
        claude_session_id: Optional[str] = None
    ) -> Session:
        """向会话添加消息"""
        session = await self.get_or_create_session(session_id)

        # 更新Claude会话ID
        if claude_session_id:
            session.claude_session_id = claude_session_id
            # 更新数据库中的Claude session ID
            self.db_manager.update_session(session_id, {
                'claude_session_id': claude_session_id,
                'last_activity': datetime.now().isoformat()
            })

        # 更新活动时间
        session.update_activity()
        
        # 更新数据库中的最后活动时间
        await self.db_manager.update_session(session_id, {
            'last_activity': session.last_activity.isoformat()
        })

        # 记录消息到数据库
        await self.db_manager.add_message_to_session(
            session_id=session_id,
            role=message.role.value,
            content=message.content,
            claude_session_id=claude_session_id
        )

        logger.debug(f"Message added to session and database", extra={
            'session_id': session_id,
            'message_role': message.role.value,
            'message_count': session.message_count
        })

        return session

    async def get_active_sessions(self) -> List[Session]:
        """获取所有活跃会话"""
        active_sessions = []
        for session in list(self.sessions.values()):
            if session.is_active and not session.is_expired():
                active_sessions.append(session)
            elif session.is_expired():
                await self.remove_session(session.session_id)

        return active_sessions

    async def get_expired_sessions(self) -> List[Session]:
        """获取过期会话"""
        expired_sessions = []
        for session in self.sessions.values():
            if session.is_expired():
                expired_sessions.append(session)

        return expired_sessions

    async def cleanup_expired_sessions(self) -> int:
        """清理过期会话"""
        expired_sessions = await self.get_expired_sessions()
        cleaned_count = 0

        for session in expired_sessions:
            if await self.remove_session(session.session_id):
                cleaned_count += 1

        if cleaned_count > 0:
            self.stats['total_sessions_cleaned'] += cleaned_count
            logger.info(f"Cleaned up expired sessions", extra={
                'cleaned_count': cleaned_count,
                'total_active_sessions': len(await self.get_active_sessions())
            })

        return cleaned_count

    async def cleanup_all_sessions(self) -> int:
        """清理所有会话"""
        session_ids = list(self.sessions.keys())
        cleaned_count = 0

        for session_id in session_ids:
            if await self.remove_session(session_id):
                cleaned_count += 1

        logger.info(f"All sessions cleaned up", extra={
            'cleaned_count': cleaned_count
        })

        return cleaned_count

    async def _cleanup_loop(self) -> None:
        """清理循环"""
        while True:
            try:
                await asyncio.sleep(config.session_cleanup_interval)
                await self.cleanup_expired_sessions()
                self.stats['cleanup_runs'] += 1
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    def get_session_count(self) -> int:
        """获取会话总数"""
        return len(self.sessions)

    def get_active_session_count(self) -> int:
        """获取活跃会话数量"""
        return len([s for s in self.sessions.values() if s.is_active and not s.is_expired()])

    def get_stats(self) -> Dict[str, int]:
        """获取统计信息"""
        return {
            **self.stats,
            'current_total_sessions': self.get_session_count(),
            'current_active_sessions': self.get_active_session_count()
        }


# 全局会话管理器实例
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """获取全局会话管理器实例"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


async def start_session_manager() -> None:
    """启动会话管理器"""
    manager = get_session_manager()
    await manager.start()


async def stop_session_manager() -> None:
    """停止会话管理器"""
    manager = get_session_manager()
    await manager.stop()