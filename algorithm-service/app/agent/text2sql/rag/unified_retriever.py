"""
统一检索入口
整合Schema、术语、SQL示例的检索功能
"""

import logging
from typing import List, Dict, Any, Optional

from rag.models import RetrievalResult
from .schema_retriever import get_schema_retriever, retrieve_schema
from .sql_example_retriever import get_sql_example_retriever, retrieve_sql_examples

logger = logging.getLogger(__name__)


class UnifiedRetriever:
    """
    统一检索器
    提供统一的检索接口，整合多种检索能力
    """
    
    def __init__(
        self,
        enable_schema: bool = True,
        enable_terminology: bool = True,
        enable_sql_example: bool = True
    ):
        """
        初始化统一检索器
        
        Args:
            enable_schema: 是否启用Schema检索
            enable_terminology: 是否启用术语检索
            enable_sql_example: 是否启用SQL示例检索
        """
        self.enable_schema = enable_schema
        self.enable_terminology = enable_terminology
        self.enable_sql_example = enable_sql_example
        
        # 初始化各检索器
        self.schema_retriever = get_schema_retriever() if enable_schema else None
        self.sql_example_retriever = get_sql_example_retriever() if enable_sql_example else None
        
        logger.info(
            f"UnifiedRetriever初始化: "
            f"schema={enable_schema}, "
            f"terminology={enable_terminology}, "
            f"sql_example={enable_sql_example}"
        )
    
    def retrieve(
        self,
        question: str,
        retriever_types: Optional[List[str]] = None,
        top_k: int = 5,
        datasource_id: Optional[int] = None,
        datasource_type: Optional[str] = None
    ) -> RetrievalResult:
        """
        统一检索接口
        
        Args:
            question: 用户问题
            retriever_types: 检索类型列表 ["schema", "terminology", "sql_example"]
            top_k: 每种类型返回的结果数量
            datasource_id: 数据源ID（用于Schema过滤）
            datasource_type: 数据源类型（用于SQL示例过滤）
            
        Returns:
            统一检索结果
        """
        if retriever_types is None:
            retriever_types = ["schema", "terminology", "sql_example"]
        
        result = RetrievalResult()
        
        # Schema检索
        if "schema" in retriever_types and self.enable_schema and self.schema_retriever:
            try:
                result.schemas = retrieve_schema(
                    question=question,
                    top_k=top_k,
                    datasource_id=datasource_id
                )
                logger.debug(f"Schema检索: 找到 {len(result.schemas)} 个结果")
            except Exception as e:
                logger.warning(f"Schema检索失败: {e}")
        
        # SQL示例检索
        if "sql_example" in retriever_types and self.enable_sql_example and self.sql_example_retriever:
            try:
                result.sql_examples = retrieve_sql_examples(
                    question=question,
                    top_k=top_k,
                    datasource_type=datasource_type
                )
                logger.debug(f"SQL示例检索: 找到 {len(result.sql_examples)} 个结果")
            except Exception as e:
                logger.warning(f"SQL示例检索失败: {e}")
        
        # 术语检索（预留接口，后续实现）
        if "terminology" in retriever_types and self.enable_terminology:
            # TODO: 实现术语检索
            logger.debug("术语检索暂未实现")
        
        return result
    
    def get_retrieval_status(self) -> Dict[str, Any]:
        """
        获取检索状态
        
        Returns:
            各检索器的状态信息
        """
        status = {
            "schema": {
                "enabled": self.enable_schema,
                "ready": self.schema_retriever.is_ready() if self.schema_retriever else False
            },
            "sql_example": {
                "enabled": self.enable_sql_example,
                "ready": self.sql_example_retriever.is_ready() if self.sql_example_retriever else False
            },
            "terminology": {
                "enabled": self.enable_terminology,
                "ready": False  # 暂未实现
            }
        }
        return status
    
    def is_any_ready(self) -> bool:
        """
        检查是否有任何检索器就绪
        
        Returns:
            是否有检索器就绪
        """
        if self.enable_schema and self.schema_retriever:
            if self.schema_retriever.is_ready():
                return True
        
        if self.enable_sql_example and self.sql_example_retriever:
            if self.sql_example_retriever.is_ready():
                return True
        
        return False


# 全局统一检索器实例
_unified_retriever: Optional[UnifiedRetriever] = None


def get_unified_retriever() -> UnifiedRetriever:
    """
    获取全局统一检索器实例
    
    Returns:
        UnifiedRetriever实例
    """
    global _unified_retriever
    if _unified_retriever is None:
        _unified_retriever = UnifiedRetriever()
    return _unified_retriever


def retrieve_all(
    question: str,
    top_k: int = 5,
    datasource_id: Optional[int] = None,
    datasource_type: Optional[str] = None
) -> RetrievalResult:
    """
    便捷函数：执行所有类型的检索
    
    Args:
        question: 用户问题
        top_k: 每种类型返回的结果数量
        datasource_id: 数据源ID
        datasource_type: 数据源类型
        
    Returns:
        统一检索结果
    """
    retriever = get_unified_retriever()
    return retriever.retrieve(
        question=question,
        top_k=top_k,
        datasource_id=datasource_id,
        datasource_type=datasource_type
    )
