"""
上下文构建器
构建发送到算法服务的上下文，包括候选术语和SQL示例
"""

import logging
from typing import List, Dict, Any, Optional

from .storage import ChatStorage
from .models import Terminology, SqlExample

logger = logging.getLogger(__name__)


class ContextBuilder:
    """
    上下文构建器
    从存储中查询候选内容，构建发送到算法服务的上下文
    """
    
    def __init__(self, storage: Optional[ChatStorage] = None):
        """
        初始化上下文构建器
        
        Args:
            storage: 存储实例
        """
        self.storage = storage or ChatStorage()
    
    def build_context(
        self,
        question: str,
        datasource_id: Optional[int] = None,
        max_terminologies: int = 20,
        max_sql_examples: int = 10
    ) -> Dict[str, Any]:
        """
        构建上下文
        
        Args:
            question: 用户问题
            datasource_id: 数据源ID（用于筛选）
            max_terminologies: 最大术语数量
            max_sql_examples: 最大SQL示例数量
            
        Returns:
            上下文字典
        """
        context = {
            "question": question,
            "datasource_id": datasource_id,
            "candidates": {
                "terminologies": [],
                "sql_examples": []
            }
        }
        
        # 1. 查询候选术语
        try:
            terminologies = self._get_candidate_terminologies(
                datasource_id=datasource_id,
                limit=max_terminologies
            )
            context["candidates"]["terminologies"] = [
                {
                    "id": t.id,
                    "term": t.term,
                    "description": t.description,
                    "category": t.category,
                    "synonyms": t.synonyms if hasattr(t, 'synonyms') else []
                }
                for t in terminologies
            ]
            logger.debug(f"获取 {len(terminologies)} 个候选术语")
        except Exception as e:
            logger.warning(f"获取候选术语失败: {e}")
        
        # 2. 查询候选SQL示例
        try:
            sql_examples = self._get_candidate_sql_examples(
                datasource_id=datasource_id,
                limit=max_sql_examples
            )
            context["candidates"]["sql_examples"] = [
                {
                    "id": e.id,
                    "question": e.question,
                    "sql": e.sql,
                    "description": e.description,
                    "datasource_type": e.datasource_type if hasattr(e, 'datasource_type') else None
                }
                for e in sql_examples
            ]
            logger.debug(f"获取 {len(sql_examples)} 个候选SQL示例")
        except Exception as e:
            logger.warning(f"获取候选SQL示例失败: {e}")
        
        return context
    
    def _get_candidate_terminologies(
        self,
        datasource_id: Optional[int] = None,
        limit: int = 20
    ) -> List[Terminology]:
        """
        获取候选术语
        
        Args:
            datasource_id: 数据源ID
            limit: 限制数量
            
        Returns:
            术语列表
        """
        # 优先获取与数据源相关的术语
        if datasource_id:
            terms = self.storage.list_terminologies_by_datasource(datasource_id, limit=limit)
            if len(terms) < limit:
                # 补充通用术语
                general_terms = self.storage.list_terminologies(
                    category="general",
                    limit=limit - len(terms)
                )
                terms.extend(general_terms)
            return terms
        else:
            return self.storage.list_terminologies(limit=limit)
    
    def _get_candidate_sql_examples(
        self,
        datasource_id: Optional[int] = None,
        limit: int = 10
    ) -> List[SqlExample]:
        """
        获取候选SQL示例
        
        Args:
            datasource_id: 数据源ID
            limit: 限制数量
            
        Returns:
            SQL示例列表
        """
        if datasource_id:
            return self.storage.list_sql_examples_by_datasource(datasource_id, limit=limit)
        else:
            return self.storage.list_sql_examples(limit=limit)


# 便捷函数
def build_context(
    question: str,
    datasource_id: Optional[int] = None,
    storage: Optional[ChatStorage] = None
) -> Dict[str, Any]:
    """
    便捷函数：构建上下文
    
    Args:
        question: 用户问题
        datasource_id: 数据源ID
        storage: 存储实例
        
    Returns:
        上下文字典
    """
    builder = ContextBuilder(storage)
    return builder.build_context(question, datasource_id)
