"""
SQL示例同步模块
实现SQL示例在业务库和向量库之间的同步
"""

import logging
from typing import Optional

from models.sql_example import SQLExample, SQLExampleCreate
from rag.sync.sync_manager import get_sync_manager
from rag.vector_store import ChromaVectorStore

logger = logging.getLogger(__name__)


class SQLExampleSync:
    """
    SQL示例同步器
    管理SQL示例的增删改查，并同步到向量库
    """
    
    def __init__(self):
        self.vector_store: ChromaVectorStore = get_sync_manager().get_sql_example_store()
    
    def add_example(
        self,
        example: SQLExampleCreate,
        db_session=None
    ) -> SQLExample:
        """
        添加SQL示例（同步到业务库和向量库）
        
        Args:
            example: SQL示例创建模型
            db_session: 数据库会话
            
        Returns:
            创建的SQL示例（包含ID）
        """
        # 1. 写入业务库
        if db_session:
            try:
                result = db_session.execute(
                    """
                    INSERT INTO training_examples 
                    (question, sql, explanation, datasource_type, datasource_id, oid, vector_version)
                    VALUES (:question, :sql, :explanation, :datasource_type, :datasource_id, :oid, :vector_version)
                    """,
                    {
                        "question": example.question,
                        "sql": example.sql,
                        "explanation": example.explanation,
                        "datasource_type": example.datasource_type,
                        "datasource_id": example.datasource_id,
                        "oid": 1,
                        "vector_version": 1
                    }
                )
                db_session.commit()
                example_id = result.lastrowid
            except Exception as e:
                logger.error(f"写入业务库失败: {e}")
                db_session.rollback()
                raise
        else:
            import random
            example_id = random.randint(1000, 9999)
        
        # 2. 创建完整模型
        example_obj = SQLExample(
            id=example_id,
            question=example.question,
            sql=example.sql,
            explanation=example.explanation,
            datasource_type=example.datasource_type,
            datasource_id=example.datasource_id,
            oid=1,
            vector_version=1
        )
        
        # 3. 同步到向量库
        try:
            self._sync_to_vector(example_obj)
            logger.info(f"SQL示例 '{example.question[:30]}...' 已同步到向量库")
        except Exception as e:
            logger.error(f"同步到向量库失败: {e}")
        
        return example_obj
    
    def _sync_to_vector(self, example: SQLExample):
        """将SQL示例同步到向量库"""
        vector_text = example.to_vector_text()
        metadata = example.to_vector_metadata()
        metadata["vector_version"] = example.vector_version
        vector_id = f"example_{example.id}"
        
        self.vector_store.add_texts(
            texts=[vector_text],
            metadatas=[metadata],
            ids=[vector_id]
        )
    
    def delete_example(self, example_id: int, db_session=None) -> bool:
        """删除SQL示例"""
        if db_session:
            try:
                db_session.execute(
                    "DELETE FROM training_examples WHERE id = :id",
                    {"id": example_id}
                )
                db_session.commit()
            except Exception as e:
                logger.error(f"删除业务库失败: {e}")
                db_session.rollback()
                return False
        
        try:
            vector_id = f"example_{example_id}"
            self.vector_store.delete([vector_id])
            return True
        except Exception as e:
            logger.error(f"删除向量库失败: {e}")
            return False


# 便捷函数
def add_sql_example(
    question: str,
    sql: str,
    explanation: Optional[str] = None,
    datasource_type: Optional[str] = None,
    db_session=None
) -> SQLExample:
    """便捷函数：添加SQL示例"""
    sync = SQLExampleSync()
    example_create = SQLExampleCreate(
        question=question,
        sql=sql,
        explanation=explanation,
        datasource_type=datasource_type
    )
    return sync.add_example(example_create, db_session)
