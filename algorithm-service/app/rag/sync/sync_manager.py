"""
同步管理器
统一管理业务库和向量库的同步
"""

import logging
from typing import Optional, Dict, Any

from rag.vector_store import ChromaVectorStore
from rag.vector_store.embeddings import EmbeddingModel

logger = logging.getLogger(__name__)


class SyncManager:
    """
    同步管理器
    管理所有向量集合的同步操作
    """
    
    _instance: Optional["SyncManager"] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self.embedding_model = EmbeddingModel()
        
        # 初始化各集合的向量存储
        self.terminology_store = ChromaVectorStore(
            collection_name="terminologies",
            embedding_model=self.embedding_model
        )
        self.sql_example_store = ChromaVectorStore(
            collection_name="sql_examples",
            embedding_model=self.embedding_model
        )
        self.schema_store = ChromaVectorStore(
            collection_name="schemas",
            embedding_model=self.embedding_model
        )
        
        logger.info("SyncManager初始化完成")
    
    def get_terminology_store(self) -> ChromaVectorStore:
        """获取术语向量存储"""
        return self.terminology_store
    
    def get_sql_example_store(self) -> ChromaVectorStore:
        """获取SQL示例向量存储"""
        return self.sql_example_store
    
    def get_schema_store(self) -> ChromaVectorStore:
        """获取Schema向量存储"""
        return self.schema_store
    
    def get_stats(self) -> Dict[str, Any]:
        """获取各集合的统计信息"""
        return {
            "terminologies": self.terminology_store.get_collection_info(),
            "sql_examples": self.sql_example_store.get_collection_info(),
            "schemas": self.schema_store.get_collection_info()
        }
    
    def clear_all(self):
        """清空所有向量集合（谨慎使用）"""
        self.terminology_store.clear()
        self.sql_example_store.clear()
        self.schema_store.clear()
        logger.warning("已清空所有向量集合")


# 全局同步管理器实例
def get_sync_manager() -> SyncManager:
    """获取全局同步管理器实例"""
    return SyncManager()
