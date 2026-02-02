"""
会话管理模块
管理多轮对话的会话和历史记录
"""

import sqlite3
import json
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class ChatMessage:
    """聊天消息"""
    id: Optional[int] = None
    session_id: Optional[int] = None
    role: str = "user"  # user, assistant
    content: str = ""
    sql: Optional[str] = None
    timestamp: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
        }


@dataclass
class ChatSession:
    """聊天会话"""
    id: Optional[int] = None
    title: str = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    message_count: int = 0
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
        if self.updated_at is None:
            self.updated_at = self.created_at


class SessionManager:
    """
    会话管理器
    使用SQLite本地存储会话和历史记录
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        初始化会话管理器
        
        Args:
            db_path: 数据库文件路径，默认 ~/.algorithm_cli/chat_history.db
        """
        if db_path is None:
            db_path = str(Path.home() / ".algorithm_cli" / "chat_history.db")
        
        self.db_path = db_path
        self._ensure_db_dir()
        self._init_tables()
        
        self.current_session_id: Optional[int] = None
    
    def _ensure_db_dir(self):
        """确保数据库目录存在"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
    
    def _init_tables(self):
        """初始化数据库表"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 创建会话表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # 创建消息表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    sql TEXT,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                )
            """)
            
            conn.commit()
            logger.info(f"数据库表初始化完成: {self.db_path}")
    
    def create_session(self, title: Optional[str] = None) -> ChatSession:
        """
        创建新会话
        
        Args:
            title: 会话标题，如果为None则自动生成
            
        Returns:
            新创建的会话
        """
        if title is None:
            title = f"会话 {datetime.now().strftime('%m-%d %H:%M')}"
        
        now = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO sessions (title, created_at, updated_at) VALUES (?, ?, ?)",
                (title, now, now)
            )
            session_id = cursor.lastrowid
            conn.commit()
        
        session = ChatSession(
            id=session_id,
            title=title,
            created_at=now,
            updated_at=now
        )
        
        self.current_session_id = session_id
        logger.info(f"创建会话: {title} (ID: {session_id})")
        
        return session
    
    def get_session(self, session_id: int) -> Optional[ChatSession]:
        """
        获取会话信息
        
        Args:
            session_id: 会话ID
            
        Returns:
            会话信息，如果不存在返回None
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, title, created_at, updated_at FROM sessions WHERE id = ?",
                (session_id,)
            )
            row = cursor.fetchone()
            
            if row:
                # 获取消息数量
                cursor.execute(
                    "SELECT COUNT(*) FROM messages WHERE session_id = ?",
                    (session_id,)
                )
                message_count = cursor.fetchone()[0]
                
                return ChatSession(
                    id=row[0],
                    title=row[1],
                    created_at=row[2],
                    updated_at=row[3],
                    message_count=message_count
                )
        
        return None
    
    def list_sessions(self, limit: int = 10) -> List[ChatSession]:
        """
        列出所有会话
        
        Args:
            limit: 返回的最大数量
            
        Returns:
            会话列表
        """
        sessions = []
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT s.id, s.title, s.created_at, s.updated_at, COUNT(m.id)
                FROM sessions s
                LEFT JOIN messages m ON s.id = m.session_id
                GROUP BY s.id
                ORDER BY s.updated_at DESC
                LIMIT ?
                """,
                (limit,)
            )
            
            for row in cursor.fetchall():
                sessions.append(ChatSession(
                    id=row[0],
                    title=row[1],
                    created_at=row[2],
                    updated_at=row[3],
                    message_count=row[4]
                ))
        
        return sessions
    
    def add_message(
        self,
        role: str,
        content: str,
        sql: Optional[str] = None,
        session_id: Optional[int] = None
    ) -> ChatMessage:
        """
        添加消息到会话
        
        Args:
            role: 角色 (user, assistant)
            content: 消息内容
            sql: 相关的SQL语句
            session_id: 会话ID，如果为None使用当前会话
            
        Returns:
            添加的消息
        """
        if session_id is None:
            session_id = self.current_session_id
        
        if session_id is None:
            # 自动创建新会话
            session = self.create_session()
            session_id = session.id
        
        now = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 插入消息
            cursor.execute(
                """
                INSERT INTO messages (session_id, role, content, sql, timestamp)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, role, content, sql, now)
            )
            
            message_id = cursor.lastrowid
            
            # 更新会话时间
            cursor.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (now, session_id)
            )
            
            conn.commit()
        
        logger.debug(f"添加消息到会话 {session_id}: {role}")
        
        return ChatMessage(
            id=message_id,
            session_id=session_id,
            role=role,
            content=content,
            sql=sql,
            timestamp=now
        )
    
    def get_history(
        self,
        session_id: Optional[int] = None,
        limit: int = 20
    ) -> List[ChatMessage]:
        """
        获取会话历史
        
        Args:
            session_id: 会话ID，如果为None使用当前会话
            limit: 返回的最大消息数
            
        Returns:
            消息列表
        """
        if session_id is None:
            session_id = self.current_session_id
        
        if session_id is None:
            return []
        
        messages = []
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, session_id, role, content, sql, timestamp
                FROM messages
                WHERE session_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (session_id, limit)
            )
            
            for row in cursor.fetchall():
                messages.append(ChatMessage(
                    id=row[0],
                    session_id=row[1],
                    role=row[2],
                    content=row[3],
                    sql=row[4],
                    timestamp=row[5]
                ))
        
        # 按时间正序返回
        messages.reverse()
        return messages
    
    def clear_history(self, session_id: Optional[int] = None):
        """
        清空会话历史
        
        Args:
            session_id: 会话ID，如果为None使用当前会话
        """
        if session_id is None:
            session_id = self.current_session_id
        
        if session_id is None:
            return
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM messages WHERE session_id = ?",
                (session_id,)
            )
            conn.commit()
        
        logger.info(f"清空会话 {session_id} 的历史")
    
    def delete_session(self, session_id: int):
        """
        删除会话
        
        Args:
            session_id: 会话ID
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 先删除消息
            cursor.execute(
                "DELETE FROM messages WHERE session_id = ?",
                (session_id,)
            )
            
            # 删除会话
            cursor.execute(
                "DELETE FROM sessions WHERE id = ?",
                (session_id,)
            )
            
            conn.commit()
        
        if self.current_session_id == session_id:
            self.current_session_id = None
        
        logger.info(f"删除会话: {session_id}")
    
    def switch_session(self, session_id: int) -> bool:
        """
        切换到指定会话
        
        Args:
            session_id: 会话ID
            
        Returns:
            是否切换成功
        """
        session = self.get_session(session_id)
        if session:
            self.current_session_id = session_id
            logger.info(f"切换到会话: {session.title} (ID: {session_id})")
            return True
        return False
    
    def get_current_session(self) -> Optional[ChatSession]:
        """获取当前会话"""
        if self.current_session_id:
            return self.get_session(self.current_session_id)
        return None
    
    def update_session_title(self, session_id: int, title: str):
        """
        更新会话标题
        
        Args:
            session_id: 会话ID
            title: 新标题
        """
        now = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
                (title, now, session_id)
            )
            conn.commit()
