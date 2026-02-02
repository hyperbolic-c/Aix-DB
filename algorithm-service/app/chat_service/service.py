"""
聊天服务业务层
实现流式转发和多轮对话管理
"""

import json
import logging
from typing import AsyncGenerator, Dict, Any, Optional, List
from datetime import datetime

from .storage import ChatStorage
from .algorithm_client import AlgorithmClient
from .models import ChatSession, ChatMessage

logger = logging.getLogger(__name__)


class ChatService:
    """
    聊天服务
    管理会话、消息，并流式转发到算法服务
    """
    
    def __init__(
        self,
        storage: Optional[ChatStorage] = None,
        algorithm_client: Optional[AlgorithmClient] = None
    ):
        """
        初始化聊天服务
        
        Args:
            storage: 存储实例
            algorithm_client: 算法服务客户端
        """
        self.storage = storage or ChatStorage()
        self.algorithm = algorithm_client or AlgorithmClient()
        
        # 默认Schema和数据源配置（从文件加载）
        self._default_schema = None
        self._default_datasource = None
    
    def _load_default_config(self):
        """加载默认配置"""
        if self._default_schema is None:
            # 从文件加载Schema
            import os
            from pathlib import Path
            
            schema_path = Path(__file__).parent.parent.parent / "data" / "schema_from_excel.json"
            if schema_path.exists():
                with open(schema_path, 'r', encoding='utf-8') as f:
                    self._default_schema = json.load(f)
            else:
                self._default_schema = {"database": "final", "db_type": "sqlite", "tables": []}
        
        if self._default_datasource is None:
            db_path = "/Users/liam/LLMPro/Aix-DB/target_db/competition/final.db"
            self._default_datasource = {
                "db_type": "sqlite",
                "db_path": db_path,
                "host": "localhost",
                "port": 0,
                "database": "final",
                "username": "",
                "password": "",
            }
    
    async def send_message(
        self,
        session_id: int,
        question: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        发送消息并流式返回结果
        
        Args:
            session_id: 会话ID
            question: 用户问题
            
        Yields:
            事件字典（从算法服务转发）
        """
        # 加载默认配置
        self._load_default_config()
        
        # 1. 保存用户消息
        self.storage.add_message(session_id, "user", question)
        logger.info(f"会话 {session_id}: 用户提问 - {question}")
        
        # 2. 获取对话历史（最近10条）
        history = self.storage.get_history(session_id, limit=10)
        chat_history = [msg.to_dict() for msg in history[:-1]]  # 排除刚添加的消息
        
        # 3. 提取SQL和总结（用于保存）
        sql_result = None
        summary_result = None
        
        # 4. 获取术语和SQL示例用于RAG增强
        terminologies = self.storage.list_terminologies()
        terminology_list = [
            {"word": t.term, "description": t.description}
            for t in terminologies
        ]
        
        sql_examples = self.storage.list_sql_examples()
        training_examples = [
            {"question": e.question, "sql": e.sql, "description": e.description}
            for e in sql_examples
        ]
        
        # 5. 调用算法服务并流式转发
        try:
            async for event in self.algorithm.analyze(
                question=question,
                schema_info=self._default_schema,
                datasource_config=self._default_datasource,
                chat_history=chat_history if chat_history else None,
                terminologies=terminology_list if terminology_list else None,
                training_examples=training_examples if training_examples else None
            ):
                # 转发事件
                yield event
                
                # 提取关键信息
                event_type = event.get("event_type", "")
                data = event.get("data", {})
                
                if event_type == "sql_generated":
                    sql_result = data.get("sql", "")
                elif event_type == "summary":
                    summary_result = data.get("text", "")
            
            # 5. 保存助手回复
            assistant_content = summary_result or "处理完成"
            self.storage.add_message(
                session_id,
                "assistant",
                assistant_content,
                sql=sql_result
            )
            logger.info(f"会话 {session_id}: 助手回复已保存")
            
        except Exception as e:
            logger.error(f"处理消息时出错: {e}")
            yield {
                "event_type": "error",
                "message": f"处理失败: {str(e)}",
                "data": {"error_type": "processing_error"}
            }
    
    def create_session(self, title: Optional[str] = None) -> ChatSession:
        """创建新会话"""
        return self.storage.create_session(title)
    
    def get_session(self, session_id: int) -> Optional[ChatSession]:
        """获取会话"""
        return self.storage.get_session(session_id)
    
    def list_sessions(self, limit: int = 20):
        """列出会话"""
        return self.storage.list_sessions(limit)
    
    def get_history(self, session_id: int, limit: int = 20):
        """获取历史"""
        return self.storage.get_history(session_id, limit)
    
    def delete_session(self, session_id: int):
        """删除会话"""
        self.storage.delete_session(session_id)
    
    def clear_history(self, session_id: int):
        """清空历史"""
        self.storage.clear_history(session_id)
    
    def rename_session(self, session_id: int, title: str):
        """重命名会话"""
        self.storage.update_session_title(session_id, title)
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        algorithm_health = await self.algorithm.health_check()
        return {
            "status": "healthy" if algorithm_health.get("status") == "healthy" else "degraded",
            "algorithm_service": algorithm_health,
            "storage": "healthy"
        }
    
    def get_terminologies(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取术语列表"""
        terminologies = self.storage.list_terminologies(category=category)
        return [
            {
                "id": t.id,
                "term": t.term,
                "description": t.description,
                "category": t.category
            }
            for t in terminologies
        ]
    
    def get_sql_examples(self, datasource_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取SQL示例列表"""
        examples = self.storage.list_sql_examples(datasource_id=datasource_id)
        return [
            {
                "id": e.id,
                "question": e.question,
                "sql": e.sql,
                "description": e.description,
                "datasource_id": e.datasource_id
            }
            for e in examples
        ]
    
    def add_terminology(self, term: str, description: str, category: Optional[str] = None) -> Dict[str, Any]:
        """添加术语"""
        terminology = self.storage.add_terminology(term, description, category)
        return {
            "id": terminology.id,
            "term": terminology.term,
            "description": terminology.description,
            "category": terminology.category
        }
    
    def update_terminology(
        self,
        term_id: int,
        term: Optional[str] = None,
        description: Optional[str] = None,
        category: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """更新术语"""
        terminology = self.storage.update_terminology(term_id, term, description, category)
        if terminology:
            return {
                "id": terminology.id,
                "term": terminology.term,
                "description": terminology.description,
                "category": terminology.category
            }
        return None
    
    def delete_terminology(self, term_id: int) -> bool:
        """删除术语"""
        return self.storage.delete_terminology(term_id)
    
    def add_sql_example(
        self,
        question: str,
        sql: str,
        description: Optional[str] = None,
        datasource_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """添加SQL示例"""
        example = self.storage.add_sql_example(question, sql, description, datasource_id)
        return {
            "id": example.id,
            "question": example.question,
            "sql": example.sql,
            "description": example.description,
            "datasource_id": example.datasource_id
        }
    
    def update_sql_example(
        self,
        example_id: int,
        question: Optional[str] = None,
        sql: Optional[str] = None,
        description: Optional[str] = None,
        datasource_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """更新SQL示例"""
        example = self.storage.update_sql_example(example_id, question, sql, description, datasource_id)
        if example:
            return {
                "id": example.id,
                "question": example.question,
                "sql": example.sql,
                "description": example.description,
                "datasource_id": example.datasource_id
            }
        return None
    
    def delete_sql_example(self, example_id: int) -> bool:
        """删除SQL示例"""
        return self.storage.delete_sql_example(example_id)
