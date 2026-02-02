"""
聊天服务存储模块
使用SQLite存储会话和消息
"""

import sqlite3
import logging
from datetime import datetime
from typing import List, Optional
from pathlib import Path

from .models import ChatSession, ChatMessage, Terminology, SqlExample

logger = logging.getLogger(__name__)


class ChatStorage:
    """
    聊天存储管理器
    使用SQLite本地存储会话和消息
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        初始化存储管理器
        
        Args:
            db_path: 数据库文件路径，默认 data/chat_history.db
        """
        if db_path is None:
            # 使用项目目录下的data文件夹
            db_path = str(Path(__file__).parent.parent.parent / "data" / "chat_history.db")
        
        self.db_path = db_path
        self._ensure_db_dir()
        self._init_tables()
        
        logger.info(f"聊天存储初始化完成: {self.db_path}")
    
    def _ensure_db_dir(self):
        """确保数据库目录存在"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
    
    def _init_tables(self):
        """初始化数据库表"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 创建会话表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 创建消息表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    sql TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
                )
            """)
            
            # 创建索引
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_session 
                ON chat_messages(session_id)
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS terminologies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    term TEXT NOT NULL UNIQUE,
                    description TEXT NOT NULL,
                    category TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sql_examples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question TEXT NOT NULL,
                    sql TEXT NOT NULL,
                    description TEXT,
                    datasource_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_terminologies_category 
                ON terminologies(category)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_sql_examples_datasource 
                ON sql_examples(datasource_id)
            """)
            
            conn.commit()
    
    def create_session(self, title: Optional[str] = None) -> ChatSession:
        """创建新会话"""
        if title is None:
            title = f"会话 {datetime.now().strftime('%m-%d %H:%M')}"
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO chat_sessions (title) VALUES (?)",
                (title,)
            )
            session_id = cursor.lastrowid
            conn.commit()
        
        return ChatSession(
            id=session_id,
            title=title,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            message_count=0
        )
    
    def get_session(self, session_id: int) -> Optional[ChatSession]:
        """获取会话信息"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT s.id, s.title, s.created_at, s.updated_at, COUNT(m.id)
                FROM chat_sessions s
                LEFT JOIN chat_messages m ON s.id = m.session_id
                WHERE s.id = ?
                GROUP BY s.id
                """,
                (session_id,)
            )
            row = cursor.fetchone()
            
            if row:
                return ChatSession(
                    id=row[0],
                    title=row[1],
                    created_at=datetime.fromisoformat(row[2]) if isinstance(row[2], str) else row[2],
                    updated_at=datetime.fromisoformat(row[3]) if isinstance(row[3], str) else row[3],
                    message_count=row[4]
                )
        return None
    
    def list_sessions(self, limit: int = 20) -> List[ChatSession]:
        """列出所有会话"""
        sessions = []
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT s.id, s.title, s.created_at, s.updated_at, COUNT(m.id)
                FROM chat_sessions s
                LEFT JOIN chat_messages m ON s.id = m.session_id
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
                    created_at=datetime.fromisoformat(row[2]) if isinstance(row[2], str) else row[2],
                    updated_at=datetime.fromisoformat(row[3]) if isinstance(row[3], str) else row[3],
                    message_count=row[4]
                ))
        
        return sessions
    
    def add_message(
        self,
        session_id: int,
        role: str,
        content: str,
        sql: Optional[str] = None
    ) -> ChatMessage:
        """添加消息到会话"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 插入消息
            cursor.execute(
                """
                INSERT INTO chat_messages (session_id, role, content, sql)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, role, content, sql)
            )
            message_id = cursor.lastrowid
            
            # 更新会话时间
            cursor.execute(
                "UPDATE chat_sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (session_id,)
            )
            
            conn.commit()
        
        return ChatMessage(
            id=message_id,
            session_id=session_id,
            role=role,
            content=content,
            sql=sql
        )
    
    def get_history(
        self,
        session_id: int,
        limit: int = 20
    ) -> List[ChatMessage]:
        """获取会话历史"""
        messages = []
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, session_id, role, content, sql, timestamp
                FROM chat_messages
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
                    timestamp=datetime.fromisoformat(row[5]) if isinstance(row[5], str) else row[5]
                ))
        
        # 按时间正序返回
        messages.reverse()
        return messages
    
    def clear_history(self, session_id: int):
        """清空会话历史"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM chat_messages WHERE session_id = ?",
                (session_id,)
            )
            conn.commit()
    
    def delete_session(self, session_id: int):
        """删除会话"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM chat_sessions WHERE id = ?",
                (session_id,)
            )
            conn.commit()
    
    def update_session_title(self, session_id: int, title: str):
        """更新会话标题"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE chat_sessions SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (title, session_id)
            )
            conn.commit()
    
    def add_terminology(self, term: str, description: str, category: Optional[str] = None) -> Terminology:
        """添加术语"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO terminologies (term, description, category)
                VALUES (?, ?, ?)
                """,
                (term, description, category)
            )
            term_id = cursor.lastrowid
            conn.commit()
        
        return Terminology(
            id=term_id,
            term=term,
            description=description,
            category=category
        )
    
    def get_terminology(self, term_id: int) -> Optional[Terminology]:
        """获取术语"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, term, description, category, created_at, updated_at FROM terminologies WHERE id = ?",
                (term_id,)
            )
            row = cursor.fetchone()
            
            if row:
                return Terminology(
                    id=row[0],
                    term=row[1],
                    description=row[2],
                    category=row[3],
                    created_at=datetime.fromisoformat(row[4]) if isinstance(row[4], str) else row[4],
                    updated_at=datetime.fromisoformat(row[5]) if isinstance(row[5], str) else row[5]
                )
        return None
    
    def get_terminology_by_term(self, term: str) -> Optional[Terminology]:
        """根据术语名称获取术语"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, term, description, category, created_at, updated_at FROM terminologies WHERE term = ?",
                (term,)
            )
            row = cursor.fetchone()
            
            if row:
                return Terminology(
                    id=row[0],
                    term=row[1],
                    description=row[2],
                    category=row[3],
                    created_at=datetime.fromisoformat(row[4]) if isinstance(row[4], str) else row[4],
                    updated_at=datetime.fromisoformat(row[5]) if isinstance(row[5], str) else row[5]
                )
        return None
    
    def list_terminologies(self, category: Optional[str] = None, limit: int = 100) -> List[Terminology]:
        """列出术语"""
        terminologies = []
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            if category:
                cursor.execute(
                    """
                    SELECT id, term, description, category, created_at, updated_at
                    FROM terminologies
                    WHERE category = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (category, limit)
                )
            else:
                cursor.execute(
                    """
                    SELECT id, term, description, category, created_at, updated_at
                    FROM terminologies
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (limit,)
                )
            
            for row in cursor.fetchall():
                terminologies.append(Terminology(
                    id=row[0],
                    term=row[1],
                    description=row[2],
                    category=row[3],
                    created_at=datetime.fromisoformat(row[4]) if isinstance(row[4], str) else row[4],
                    updated_at=datetime.fromisoformat(row[5]) if isinstance(row[5], str) else row[5]
                ))
        
        return terminologies
    
    def update_terminology(
        self,
        term_id: int,
        term: Optional[str] = None,
        description: Optional[str] = None,
        category: Optional[str] = None
    ) -> Optional[Terminology]:
        """更新术语"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            updates = []
            params = []
            if term is not None:
                updates.append("term = ?")
                params.append(term)
            if description is not None:
                updates.append("description = ?")
                params.append(description)
            if category is not None:
                updates.append("category = ?")
                params.append(category)
            
            if not updates:
                return self.get_terminology(term_id)
            
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(term_id)
            
            cursor.execute(
                f"UPDATE terminologies SET {', '.join(updates)} WHERE id = ?",
                params
            )
            conn.commit()
        
        return self.get_terminology(term_id)
    
    def delete_terminology(self, term_id: int) -> bool:
        """删除术语"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM terminologies WHERE id = ?", (term_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    def add_sql_example(
        self,
        question: str,
        sql: str,
        description: Optional[str] = None,
        datasource_id: Optional[int] = None
    ) -> SqlExample:
        """添加SQL示例"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO sql_examples (question, sql, description, datasource_id)
                VALUES (?, ?, ?, ?)
                """,
                (question, sql, description, datasource_id)
            )
            example_id = cursor.lastrowid
            conn.commit()
        
        return SqlExample(
            id=example_id,
            question=question,
            sql=sql,
            description=description,
            datasource_id=datasource_id
        )
    
    def get_sql_example(self, example_id: int) -> Optional[SqlExample]:
        """获取SQL示例"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, question, sql, description, datasource_id, created_at, updated_at
                FROM sql_examples WHERE id = ?
                """,
                (example_id,)
            )
            row = cursor.fetchone()
            
            if row:
                return SqlExample(
                    id=row[0],
                    question=row[1],
                    sql=row[2],
                    description=row[3],
                    datasource_id=row[4],
                    created_at=datetime.fromisoformat(row[5]) if isinstance(row[5], str) else row[5],
                    updated_at=datetime.fromisoformat(row[6]) if isinstance(row[6], str) else row[6]
                )
        return None
    
    def list_sql_examples(
        self,
        datasource_id: Optional[int] = None,
        limit: int = 100
    ) -> List[SqlExample]:
        """列出SQL示例"""
        examples = []
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            if datasource_id is not None:
                cursor.execute(
                    """
                    SELECT id, question, sql, description, datasource_id, created_at, updated_at
                    FROM sql_examples
                    WHERE datasource_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (datasource_id, limit)
                )
            else:
                cursor.execute(
                    """
                    SELECT id, question, sql, description, datasource_id, created_at, updated_at
                    FROM sql_examples
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (limit,)
                )
            
            for row in cursor.fetchall():
                examples.append(SqlExample(
                    id=row[0],
                    question=row[1],
                    sql=row[2],
                    description=row[3],
                    datasource_id=row[4],
                    created_at=datetime.fromisoformat(row[5]) if isinstance(row[5], str) else row[5],
                    updated_at=datetime.fromisoformat(row[6]) if isinstance(row[6], str) else row[6]
                ))
        
        return examples
    
    def update_sql_example(
        self,
        example_id: int,
        question: Optional[str] = None,
        sql: Optional[str] = None,
        description: Optional[str] = None,
        datasource_id: Optional[int] = None
    ) -> Optional[SqlExample]:
        """更新SQL示例"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            updates = []
            params = []
            if question is not None:
                updates.append("question = ?")
                params.append(question)
            if sql is not None:
                updates.append("sql = ?")
                params.append(sql)
            if description is not None:
                updates.append("description = ?")
                params.append(description)
            if datasource_id is not None:
                updates.append("datasource_id = ?")
                params.append(datasource_id)
            
            if not updates:
                return self.get_sql_example(example_id)
            
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(example_id)
            
            cursor.execute(
                f"UPDATE sql_examples SET {', '.join(updates)} WHERE id = ?",
                params
            )
            conn.commit()
        
        return self.get_sql_example(example_id)
    
    def delete_sql_example(self, example_id: int) -> bool:
        """删除SQL示例"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM sql_examples WHERE id = ?", (example_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    def list_terminologies_by_datasource(
        self,
        datasource_id: int,
        limit: int = 100
    ) -> List[Terminology]:
        """
        按数据源列出术语
        注意：当前terminologies表没有datasource_id字段，
        这里假设通过category或其他方式关联，或者返回所有术语
        """
        # 目前返回所有术语，后续可以添加datasource_id关联
        return self.list_terminologies(limit=limit)
