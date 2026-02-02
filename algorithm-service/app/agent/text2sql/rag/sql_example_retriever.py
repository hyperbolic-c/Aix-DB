"""
SQL示例向量检索器
基于问题检索相似的SQL示例
"""

import logging
from typing import List, Dict, Any, Optional

from rag.vector_store import ChromaVectorStore
from rag.models import SQLExampleResult

logger = logging.getLogger(__name__)


class SQLExampleRetriever:
    """
    SQL示例检索器
    基于向量相似度检索相似的SQL查询示例
    """
    
    COLLECTION_NAME = "sql_example_store"
    
    def __init__(
        self,
        vector_store: Optional[ChromaVectorStore] = None,
        top_k: int = 5
    ):
        """
        初始化 SQL 示例检索器
        
        Args:
            vector_store: 向量存储实例
            top_k: 默认返回结果数量
        """
        self.vector_store = vector_store or ChromaVectorStore(
            collection_name=self.COLLECTION_NAME
        )
        self.top_k = top_k
        logger.info(f"SQLExampleRetriever初始化: top_k={top_k}")
    
    def retrieve(
        self,
        question: str,
        top_k: Optional[int] = None,
        datasource_type: Optional[str] = None
    ) -> List[SQLExampleResult]:
        """
        基于问题检索相似SQL示例
        
        Args:
            question: 用户问题
            top_k: 返回结果数量
            datasource_type: 数据源类型过滤
            
        Returns:
            SQL示例检索结果列表
        """
        k = top_k or self.top_k
        
        try:
            # 检查向量存储是否为空
            if self.vector_store.is_empty():
                logger.warning("SQL示例向量存储为空，请先构建索引")
                return []
            
            # 构建过滤条件
            filter_condition = None
            if datasource_type:
                filter_condition = {"datasource_type": datasource_type}
            
            # 执行相似性搜索
            results = self.vector_store.similarity_search(
                query=question,
                k=k,
                filter=filter_condition
            )
            
            # 解析结果
            example_results = []
            for text, score, metadata in results:
                result = SQLExampleResult(
                    question=metadata.get("question", ""),
                    sql=metadata.get("sql", ""),
                    explanation=metadata.get("explanation", ""),
                    datasource_type=metadata.get("datasource_type", ""),
                    relevance_score=score
                )
                example_results.append(result)
            
            logger.debug(f"SQL示例检索完成: 找到 {len(example_results)} 个相似示例")
            return example_results
            
        except Exception as e:
            logger.error(f"SQL示例检索失败: {e}")
            return []
    
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
            "is_ready": self.is_ready()
        }


# 全局检索器实例
_sql_example_retriever: Optional[SQLExampleRetriever] = None


def get_sql_example_retriever() -> SQLExampleRetriever:
    """
    获取全局SQL示例检索器实例
    
    Returns:
        SQLExampleRetriever实例
    """
    global _sql_example_retriever
    if _sql_example_retriever is None:
        _sql_example_retriever = SQLExampleRetriever()
    return _sql_example_retriever


def retrieve_sql_examples(
    question: str,
    top_k: int = 5,
    datasource_type: Optional[str] = None
) -> List[SQLExampleResult]:
    """
    便捷函数：检索SQL示例
    
    Args:
        question: 用户问题
        top_k: 返回结果数量
        datasource_type: 数据源类型过滤
        
    Returns:
        SQL示例检索结果列表
    """
    retriever = get_sql_example_retriever()
    return retriever.retrieve(question, top_k=top_k, datasource_type=datasource_type)
