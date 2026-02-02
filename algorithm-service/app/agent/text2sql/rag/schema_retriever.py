"""
Schema 向量检索器
基于问题检索相关的表和字段
"""

import logging
from typing import List, Dict, Any, Optional

from rag.vector_store import ChromaVectorStore
from rag.models import SchemaRetrievalResult

logger = logging.getLogger(__name__)


class SchemaRetriever:
    """
    Schema 检索器
    基于向量相似度检索相关的表和字段
    """
    
    COLLECTION_NAME = "schema_store"
    
    def __init__(
        self,
        vector_store: Optional[ChromaVectorStore] = None,
        top_k: int = 5
    ):
        """
        初始化 Schema 检索器
        
        Args:
            vector_store: 向量存储实例
            top_k: 默认返回结果数量
        """
        self.vector_store = vector_store or ChromaVectorStore(
            collection_name=self.COLLECTION_NAME
        )
        self.top_k = top_k
        logger.info(f"SchemaRetriever初始化: top_k={top_k}")
    
    def retrieve(
        self,
        question: str,
        top_k: Optional[int] = None,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[SchemaRetrievalResult]:
        """
        基于问题检索相关Schema
        
        Args:
            question: 用户问题
            top_k: 返回结果数量
            filter: 过滤条件
            
        Returns:
            Schema检索结果列表
        """
        k = top_k or self.top_k
        
        try:
            # 检查向量存储是否为空
            if self.vector_store.is_empty():
                logger.warning("Schema向量存储为空，请先构建索引")
                return []
            
            # 执行相似性搜索
            results = self.vector_store.similarity_search(
                query=question,
                k=k,
                filter=filter
            )
            
            # 解析结果
            schema_results = []
            for text, score, metadata in results:
                result = SchemaRetrievalResult(
                    table_name=metadata.get("table_name", ""),
                    table_description=metadata.get("table_description", ""),
                    columns=metadata.get("columns", []),
                    relevance_score=score,
                    metadata=metadata
                )
                schema_results.append(result)
            
            logger.debug(f"Schema检索完成: 找到 {len(schema_results)} 个相关表")
            return schema_results
            
        except Exception as e:
            logger.error(f"Schema检索失败: {e}")
            return []
    
    def retrieve_with_columns(
        self,
        question: str,
        top_k_tables: int = 3,
        top_k_columns: int = 10
    ) -> List[SchemaRetrievalResult]:
        """
        检索表和字段（分别检索后合并）
        
        Args:
            question: 用户问题
            top_k_tables: 返回表数量
            top_k_columns: 每个表返回的字段数量
            
        Returns:
            Schema检索结果列表
        """
        # 先检索表级别
        table_results = self.retrieve(
            question=question,
            top_k=top_k_tables,
            filter={"type": "table"}
        )
        
        if not table_results:
            return []
        
        # 对每个表检索相关字段
        enhanced_results = []
        for table in table_results:
            table_name = table.table_name
            
            # 检索该表的相关字段
            column_results = self.retrieve(
                question=question,
                top_k=top_k_columns,
                filter={"type": "column", "table_name": table_name}
            )
            
            # 合并字段信息
            if column_results:
                table.columns = [col.metadata for col in column_results]
            
            enhanced_results.append(table)
        
        return enhanced_results
    
    def is_ready(self) -> bool:
        """
        检查检索器是否就绪
        
        Returns:
            是否已构建索引
        """
        return not self.vector_store.is_empty()
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            统计信息字典
        """
        info = self.vector_store.get_collection_info()
        return {
            "collection_name": info["name"],
            "document_count": info["count"],
            "embedding_dimension": info["embedding_dimension"],
            "is_ready": self.is_ready()
        }


# 全局检索器实例（单例模式）
_schema_retriever: Optional[SchemaRetriever] = None


def get_schema_retriever() -> SchemaRetriever:
    """
    获取全局Schema检索器实例
    
    Returns:
        SchemaRetriever实例
    """
    global _schema_retriever
    if _schema_retriever is None:
        _schema_retriever = SchemaRetriever()
    return _schema_retriever


def retrieve_schema(
    question: str,
    top_k: int = 5,
    datasource_id: Optional[int] = None
) -> List[SchemaRetrievalResult]:
    """
    便捷函数：检索Schema
    
    Args:
        question: 用户问题
        top_k: 返回结果数量
        datasource_id: 数据源ID（用于过滤）
        
    Returns:
        Schema检索结果列表
    """
    retriever = get_schema_retriever()
    
    # 构建过滤条件
    filter_condition = None
    if datasource_id:
        filter_condition = {"datasource_id": datasource_id}
    
    return retriever.retrieve(question, top_k=top_k, filter=filter_condition)
