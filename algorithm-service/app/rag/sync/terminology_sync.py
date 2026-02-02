"""
术语同步模块
实现术语在业务库和向量库之间的同步
"""

import logging
from typing import Optional, List

from models.terminology import Terminology, TerminologyCreate
from rag.sync.sync_manager import get_sync_manager
from rag.vector_store import ChromaVectorStore

logger = logging.getLogger(__name__)


class TerminologySync:
    """
    术语同步器
    管理术语的增删改查，并同步到向量库
    """
    
    def __init__(self):
        self.vector_store: ChromaVectorStore = get_sync_manager().get_terminology_store()
    
    def add_terminology(
        self,
        terminology: TerminologyCreate,
        db_session=None
    ) -> Terminology:
        """
        添加术语（同步到业务库和向量库）
        
        Args:
            terminology: 术语创建模型
            db_session: 数据库会话
            
        Returns:
            创建的术语（包含ID）
        """
        # 1. 写入业务库
        if db_session:
            # 如果有数据库会话，使用SQLAlchemy写入
            from model.db_connection_pool import get_db_pool
            
            try:
                # 插入业务库
                result = db_session.execute(
                    """
                    INSERT INTO terminologies 
                    (term, definition, category, synonyms, datasource_id, oid, vector_version)
                    VALUES (:term, :definition, :category, :synonyms, :datasource_id, :oid, :vector_version)
                    """,
                    {
                        "term": terminology.term,
                        "definition": terminology.definition,
                        "category": terminology.category,
                        "synonyms": str(terminology.synonyms),
                        "datasource_id": terminology.datasource_id,
                        "oid": 1,
                        "vector_version": 1
                    }
                )
                db_session.commit()
                terminology_id = result.lastrowid
                
            except Exception as e:
                logger.error(f"写入业务库失败: {e}")
                db_session.rollback()
                raise
        else:
            # 如果没有数据库会话，仅生成ID（用于测试）
            import random
            terminology_id = random.randint(1000, 9999)
        
        # 2. 创建完整模型
        term_obj = Terminology(
            id=terminology_id,
            term=terminology.term,
            definition=terminology.definition,
            category=terminology.category,
            synonyms=terminology.synonyms,
            datasource_id=terminology.datasource_id,
            oid=1,
            vector_version=1
        )
        
        # 3. 同步到向量库
        try:
            self._sync_to_vector(term_obj)
            logger.info(f"术语 '{terminology.term}' 已同步到向量库")
        except Exception as e:
            logger.error(f"同步到向量库失败: {e}")
            # 这里可以选择回滚业务库操作，或者记录错误稍后重试
        
        return term_obj
    
    def _sync_to_vector(self, terminology: Terminology):
        """
        将术语同步到向量库
        
        Args:
            terminology: 术语模型
        """
        # 生成向量文本
        vector_text = terminology.to_vector_text()
        
        # 生成元数据
        metadata = terminology.to_vector_metadata()
        metadata["vector_version"] = terminology.vector_version
        
        # 生成唯一ID
        vector_id = f"term_{terminology.id}"
        
        # 添加到向量库
        self.vector_store.add_texts(
            texts=[vector_text],
            metadatas=[metadata],
            ids=[vector_id]
        )
    
    def update_terminology(
        self,
        term_id: int,
        updates: dict,
        db_session=None
    ) -> bool:
        """
        更新术语
        
        Args:
            term_id: 术语ID
            updates: 更新字段
            db_session: 数据库会话
            
        Returns:
            是否成功
        """
        # 1. 更新业务库
        if db_session:
            try:
                db_session.execute(
                    """
                    UPDATE terminologies 
                    SET term = COALESCE(:term, term),
                        definition = COALESCE(:definition, definition),
                        category = COALESCE(:category, category),
                        synonyms = COALESCE(:synonyms, synonyms),
                        vector_version = vector_version + 1
                    WHERE id = :id
                    """,
                    {"id": term_id, **updates}
                )
                db_session.commit()
            except Exception as e:
                logger.error(f"更新业务库失败: {e}")
                db_session.rollback()
                return False
        
        # 2. 更新向量库（先删除再添加）
        try:
            vector_id = f"term_{term_id}"
            self.vector_store.delete([vector_id])
            
            # 重新获取完整数据并同步
            if db_session:
                result = db_session.execute(
                    "SELECT * FROM terminologies WHERE id = :id",
                    {"id": term_id}
                ).fetchone()
                
                if result:
                    term_obj = Terminology(
                        id=result.id,
                        term=result.term,
                        definition=result.definition,
                        category=result.category,
                        synonyms=eval(result.synonyms) if result.synonyms else [],
                        vector_version=result.vector_version
                    )
                    self._sync_to_vector(term_obj)
            
            logger.info(f"术语 ID={term_id} 已更新到向量库")
            return True
        except Exception as e:
            logger.error(f"更新向量库失败: {e}")
            return False
    
    def delete_terminology(self, term_id: int, db_session=None) -> bool:
        """
        删除术语
        
        Args:
            term_id: 术语ID
            db_session: 数据库会话
            
        Returns:
            是否成功
        """
        # 1. 删除业务库
        if db_session:
            try:
                db_session.execute(
                    "DELETE FROM terminologies WHERE id = :id",
                    {"id": term_id}
                )
                db_session.commit()
            except Exception as e:
                logger.error(f"删除业务库失败: {e}")
                db_session.rollback()
                return False
        
        # 2. 删除向量库
        try:
            vector_id = f"term_{term_id}"
            self.vector_store.delete([vector_id])
            logger.info(f"术语 ID={term_id} 已从向量库删除")
            return True
        except Exception as e:
            logger.error(f"删除向量库失败: {e}")
            return False
    
    def batch_sync_from_db(self, db_session=None) -> int:
        """
        从业务库批量同步所有术语到向量库
        
        Args:
            db_session: 数据库会话
            
        Returns:
            同步的数量
        """
        if not db_session:
            logger.warning("没有数据库会话，跳过批量同步")
            return 0
        
        try:
            # 清空向量库
            self.vector_store.clear()
            
            # 获取所有术语
            results = db_session.execute(
                "SELECT * FROM terminologies"
            ).fetchall()
            
            count = 0
            for result in results:
                term_obj = Terminology(
                    id=result.id,
                    term=result.term,
                    definition=result.definition,
                    category=result.category,
                    synonyms=eval(result.synonyms) if result.synonyms else [],
                    datasource_id=result.datasource_id,
                    oid=result.oid,
                    vector_version=result.vector_version
                )
                self._sync_to_vector(term_obj)
                count += 1
            
            logger.info(f"批量同步完成: {count} 个术语")
            return count
        except Exception as e:
            logger.error(f"批量同步失败: {e}")
            return 0


# 便捷函数
def add_terminology(
    term: str,
    definition: str,
    category: Optional[str] = None,
    synonyms: Optional[List[str]] = None,
    datasource_id: Optional[int] = None,
    db_session=None
) -> Terminology:
    """
    便捷函数：添加术语
    
    Args:
        term: 术语名称
        definition: 定义
        category: 分类
        synonyms: 同义词
        datasource_id: 数据源ID
        db_session: 数据库会话
        
    Returns:
        创建的术语
    """
    sync = TerminologySync()
    terminology_create = TerminologyCreate(
        term=term,
        definition=definition,
        category=category,
        synonyms=synonyms or [],
        datasource_id=datasource_id
    )
    return sync.add_terminology(terminology_create, db_session)
