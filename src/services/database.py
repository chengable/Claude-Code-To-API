"""
SQLite数据库管理模块
用于持久化存储session信息和映射关系
"""

import sqlite3
import asyncio
import aiosqlite
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from pathlib import Path
import json

from ..utils.config import config

logger = logging.getLogger(__name__)


class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, db_path: Optional[str] = None):
        """初始化数据库管理器"""
        if db_path is None:
            # 默认数据库路径
            db_dir = Path.home() / ".claude-web" / "data"
            db_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(db_dir / "sessions.db")
        
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()
        
    async def initialize(self) -> None:
        """初始化数据库和表结构"""
        async with self._lock:
            self._connection = await aiosqlite.connect(self.db_path)
            await self._create_tables()
            logger.info(f"Database initialized at {self.db_path}")
    
    async def close(self) -> None:
        """关闭数据库连接"""
        async with self._lock:
            if self._connection:
                await self._connection.close()
                self._connection = None
                logger.info("Database connection closed")
    
    async def _create_tables(self) -> None:
        """创建数据库表"""
        # sessions表：存储session基本信息
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                claude_session_id TEXT,
                claude_process_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                message_count INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT 1,
                claude_working_dir TEXT,
                max_message_history INTEGER DEFAULT 50,
                timeout_minutes INTEGER DEFAULT 30,
                user_agent TEXT,
                client_ip TEXT,
                metadata TEXT  -- JSON格式存储额外元数据
            )
        """)
        
        # session_messages表：存储session的消息历史
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS session_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                claude_session_id TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions (session_id) ON DELETE CASCADE
            )
        """)
        
        # 创建索引以提高查询性能
        await self._connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_last_activity 
            ON sessions (last_activity)
        """)
        
        await self._connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_is_active 
            ON sessions (is_active)
        """)
        
        await self._connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_session_messages_session_id 
            ON session_messages (session_id)
        """)
        
        await self._connection.commit()
        logger.info("Database tables created successfully")
    
    async def create_session(self, session_data: Dict[str, Any]) -> bool:
        """创建新session"""
        try:
            async with self._lock:
                # 准备数据
                metadata_json = json.dumps(session_data.get('metadata', {}))
                
                await self._connection.execute("""
                    INSERT INTO sessions (
                        session_id, claude_session_id, claude_process_id,
                        created_at, last_activity, message_count, is_active,
                        claude_working_dir, max_message_history, timeout_minutes,
                        user_agent, client_ip, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_data['session_id'],
                    session_data.get('claude_session_id'),
                    session_data.get('claude_process_id'),
                    session_data['created_at'].isoformat(),
                    session_data['last_activity'].isoformat(),
                    session_data.get('message_count', 0),
                    session_data.get('is_active', True),
                    session_data.get('claude_working_dir'),
                    session_data.get('max_message_history', 50),
                    session_data.get('timeout_minutes', 30),
                    session_data.get('user_agent'),
                    session_data.get('client_ip'),
                    metadata_json
                ))
                
                await self._connection.commit()
                logger.info(f"Session created in database: {session_data['session_id']}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to create session in database: {e}")
            return False
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取session信息"""
        try:
            async with self._lock:
                cursor = await self._connection.execute("""
                    SELECT * FROM sessions WHERE session_id = ?
                """, (session_id,))
                
                row = await cursor.fetchone()
                if not row:
                    return None
                
                # 转换为字典
                columns = [description[0] for description in cursor.description]
                session_data = dict(zip(columns, row))
                
                # 解析JSON字段
                if session_data['metadata']:
                    session_data['metadata'] = json.loads(session_data['metadata'])
                else:
                    session_data['metadata'] = {}
                
                # 转换时间字段
                session_data['created_at'] = datetime.fromisoformat(session_data['created_at'])
                session_data['last_activity'] = datetime.fromisoformat(session_data['last_activity'])
                
                return session_data
                
        except Exception as e:
            logger.error(f"Failed to get session from database: {e}")
            return None
    
    async def update_session(self, session_id: str, updates: Dict[str, Any]) -> bool:
        """更新session信息"""
        try:
            async with self._lock:
                # 构建更新语句
                set_clauses = []
                values = []
                
                for key, value in updates.items():
                    if key == 'metadata':
                        set_clauses.append("metadata = ?")
                        values.append(json.dumps(value))
                    elif key in ['created_at', 'last_activity'] and isinstance(value, datetime):
                        set_clauses.append(f"{key} = ?")
                        values.append(value.isoformat())
                    else:
                        set_clauses.append(f"{key} = ?")
                        values.append(value)
                
                if not set_clauses:
                    return True
                
                values.append(session_id)
                
                await self._connection.execute(f"""
                    UPDATE sessions SET {', '.join(set_clauses)} WHERE session_id = ?
                """, values)
                
                await self._connection.commit()
                logger.debug(f"Session updated in database: {session_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to update session in database: {e}")
            return False
    
    async def delete_session(self, session_id: str) -> bool:
        """删除session"""
        try:
            async with self._lock:
                await self._connection.execute("""
                    DELETE FROM sessions WHERE session_id = ?
                """, (session_id,))
                
                await self._connection.commit()
                logger.info(f"Session deleted from database: {session_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to delete session from database: {e}")
            return False
    
    async def get_active_sessions(self) -> List[Dict[str, Any]]:
        """获取所有活跃的session"""
        try:
            async with self._lock:
                cursor = await self._connection.execute("""
                    SELECT * FROM sessions WHERE is_active = 1
                """)
                
                rows = await cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                
                sessions = []
                for row in rows:
                    session_data = dict(zip(columns, row))
                    
                    # 解析JSON字段
                    if session_data['metadata']:
                        session_data['metadata'] = json.loads(session_data['metadata'])
                    else:
                        session_data['metadata'] = {}
                    
                    # 转换时间字段
                    session_data['created_at'] = datetime.fromisoformat(session_data['created_at'])
                    session_data['last_activity'] = datetime.fromisoformat(session_data['last_activity'])
                    
                    sessions.append(session_data)
                
                return sessions
                
        except Exception as e:
            logger.error(f"Failed to get active sessions from database: {e}")
            return []
    
    async def get_expired_sessions(self, timeout_minutes: int = 30) -> List[str]:
        """获取过期的session ID列表"""
        try:
            async with self._lock:
                cutoff_time = datetime.now() - timedelta(minutes=timeout_minutes)
                
                cursor = await self._connection.execute("""
                    SELECT session_id FROM sessions 
                    WHERE last_activity < ? AND is_active = 1
                """, (cutoff_time.isoformat(),))
                
                rows = await cursor.fetchall()
                return [row[0] for row in rows]
                
        except Exception as e:
            logger.error(f"Failed to get expired sessions from database: {e}")
            return []
    
    async def cleanup_expired_sessions(self, timeout_minutes: int = 30) -> int:
        """清理过期的session"""
        try:
            async with self._lock:
                cutoff_time = datetime.now() - timedelta(minutes=timeout_minutes)
                
                cursor = await self._connection.execute("""
                    DELETE FROM sessions 
                    WHERE last_activity < ? AND is_active = 1
                """, (cutoff_time.isoformat(),))
                
                await self._connection.commit()
                deleted_count = cursor.rowcount
                
                logger.info(f"Cleaned up {deleted_count} expired sessions")
                return deleted_count
                
        except Exception as e:
            logger.error(f"Failed to cleanup expired sessions: {e}")
            return 0
    
    async def add_message_to_session(self, session_id: str, role: str, content: str, claude_session_id: Optional[str] = None) -> bool:
        """向session添加消息"""
        try:
            async with self._lock:
                await self._connection.execute("""
                    INSERT INTO session_messages (session_id, role, content, claude_session_id)
                    VALUES (?, ?, ?, ?)
                """, (session_id, role, content, claude_session_id))
                
                await self._connection.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to add message to session: {e}")
            return False
    
    async def get_session_messages(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """获取session的消息历史"""
        try:
            async with self._lock:
                cursor = await self._connection.execute("""
                    SELECT role, content, timestamp, claude_session_id 
                    FROM session_messages 
                    WHERE session_id = ? 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                """, (session_id, limit))
                
                rows = await cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                
                messages = []
                for row in rows:
                    message_data = dict(zip(columns, row))
                    message_data['timestamp'] = datetime.fromisoformat(message_data['timestamp'])
                    messages.append(message_data)
                
                return list(reversed(messages))  # 返回正序
                
        except Exception as e:
            logger.error(f"Failed to get session messages: {e}")
            return []


# 全局数据库管理器实例
_db_manager: Optional[DatabaseManager] = None


def get_database_manager() -> DatabaseManager:
    """获取全局数据库管理器实例"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


async def initialize_database() -> None:
    """初始化数据库"""
    manager = get_database_manager()
    await manager.initialize()


async def close_database() -> None:
    """关闭数据库"""
    manager = get_database_manager()
    await manager.close()