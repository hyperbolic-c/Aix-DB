"""
Schema同步模块
实现目标数据库Schema在首次连接时同步到向量库
"""

import json
import logging
from typing import Optional, Dict, Any

from rag.sync.sync_manager import get_sync_manager
from rag.vector_store import ChromaVectorStore

logger = logging.getLogger(__name__)


class SchemaSync:
    """
    Schema同步器
    在数据源首次连接时，将Schema同步到向量库
    """
    
    def __init__(self):
        self.vector_store: ChromaVectorStore = get_sync_manager().get_schema_store()
    
    def sync_on_first_connect(
        self,
        datasource_id: int,
        schema_info: Dict[str, Any],
        db_session=None
    ) -> bool:
        """
        首次连接时同步Schema
        
        Args:
            datasource_id: 数据源ID
            schema_info: Schema信息（从数据库获取的表结构）
            db_session: 数据库会话
            
        Returns:
            是否成功
        """
        # 1. 检查是否已同步
        if self._is_already_synced(datasource_id):
            logger.info(f"数据源 {datasource_id} 的Schema已同步，跳过")
            return True
        
        logger.info(f"开始同步数据源 {datasource_id} 的Schema到向量库")
        
        # 2. 保存Schema到业务库（可选）
        if db_session:
            try:
                # 检查是否已有记录
                existing = db_session.execute(
                    "SELECT id FROM schemas WHERE datasource_id = :datasource_id",
                    {"datasource_id": datasource_id}
                ).fetchone()
                
                if existing:
                    # 更新
                    db_session.execute(
                        "UPDATE schemas SET schema_json = :schema_json, updated_at = CURRENT_TIMESTAMP WHERE datasource_id = :datasource_id",
                        {"datasource_id": datasource_id, "schema_json": json.dumps(schema_info)}
                    )
                else:
                    # 插入
                    db_session.execute(
                        "INSERT INTO schemas (datasource_id, schema_json) VALUES (:datasource_id, :schema_json)",
                        {"datasource_id": datasource_id, "schema_json": json.dumps(schema_info)}
                    )
                db_session.commit()
                logger.info(f"Schema已保存到业务库")
            except Exception as e:
                logger.error(f"保存到业务库失败: {e}")
                # 继续同步到向量库，不阻断
        
        # 3. 同步到向量库
        try:
            self._sync_schema_to_vector(datasource_id, schema_info)
            logger.info(f"数据源 {datasource_id} 的Schema已同步到向量库")
            return True
        except Exception as e:
            logger.error(f"同步到向量库失败: {e}")
            return False
    
    def _is_already_synced(self, datasource_id: int) -> bool:
        """
        检查Schema是否已同步
        
        Args:
            datasource_id: 数据源ID
            
        Returns:
            是否已同步
        """
        try:
            # 检查向量库中是否有该数据源的Schema
            results = self.vector_store.similarity_search(
                query="",  # 空查询，只检查过滤结果
                k=1,
                filter={"datasource_id": datasource_id}
            )
            return len(results) > 0
        except Exception:
            return False
    
    def _sync_schema_to_vector(
        self,
        datasource_id: int,
        schema_info: Dict[str, Any]
    ):
        """
        将Schema同步到向量库
        
        Args:
            datasource_id: 数据源ID
            schema_info: Schema信息
        """
        tables = schema_info.get("tables", [])
        
        for table in tables:
            self._index_table(datasource_id, table)
    
    def _index_table(self, datasource_id: int, table: Dict[str, Any]):
        """
        索引单个表
        
        Args:
            datasource_id: 数据源ID
            table: 表信息
        """
        table_name = table.get("name", "")
        table_description = table.get("description", "")
        columns = table.get("columns", [])
        
        # 构建表的文本表示
        table_text = self._build_table_text(table_name, table_description, columns)
        
        # 表级别的元数据
        table_metadata = {
            "type": "table",
            "table_name": table_name,
            "table_description": table_description,
            "datasource_id": datasource_id,
            "columns": columns
        }
        
        # 索引表
        vector_id = f"schema_{datasource_id}_table_{table_name}"
        self.vector_store.add_texts(
            texts=[table_text],
            metadatas=[table_metadata],
            ids=[vector_id]
        )
        
        # 索引字段
        for column in columns:
            self._index_column(datasource_id, table_name, column)
    
    def _index_column(
        self,
        datasource_id: int,
        table_name: str,
        column: Dict[str, Any]
    ):
        """
        索引单个字段
        
        Args:
            datasource_id: 数据源ID
            table_name: 表名
            column: 字段信息
        """
        column_name = column.get("name", "")
        column_type = column.get("type", "")
        column_description = column.get("description", "")
        
        # 构建字段的文本表示
        column_text = f"表 {table_name} 的字段 {column_name}"
        if column_type:
            column_text += f"，类型为 {column_type}"
        if column_description:
            column_text += f"，{column_description}"
        
        # 字段级别的元数据
        column_metadata = {
            "type": "column",
            "table_name": table_name,
            "column_name": column_name,
            "column_type": column_type,
            "column_description": column_description,
            "datasource_id": datasource_id
        }
        
        # 索引字段
        vector_id = f"schema_{datasource_id}_column_{table_name}_{column_name}"
        self.vector_store.add_texts(
            texts=[column_text],
            metadatas=[column_metadata],
            ids=[vector_id]
        )
    
    def _build_table_text(
        self,
        table_name: str,
        table_description: str,
        columns: list
    ) -> str:
        """
        构建表的文本表示
        
        Args:
            table_name: 表名
            table_description: 表描述
            columns: 字段列表
            
        Returns:
            文本表示
        """
        text = f"表名: {table_name}"
        
        if table_description:
            text += f"\n描述: {table_description}"
        
        if columns:
            text += "\n字段:"
            for col in columns:
                col_name = col.get("name", "")
                col_type = col.get("type", "")
                col_desc = col.get("description", "")
                
                text += f"\n  - {col_name}"
                if col_type:
                    text += f" ({col_type})"
                if col_desc:
                    text += f": {col_desc}"
        
        return text
    
    def clear_schema(self, datasource_id: int) -> bool:
        """
        清除指定数据源的Schema
        
        Args:
            datasource_id: 数据源ID
            
        Returns:
            是否成功
        """
        try:
            # 获取所有该数据源的文档ID
            results = self.vector_store.similarity_search(
                query="",
                k=10000,  # 大数，获取所有
                filter={"datasource_id": datasource_id}
            )
            
            ids_to_delete = []
            for _, _, metadata in results:
                doc_id = metadata.get("id")
                if doc_id:
                    ids_to_delete.append(doc_id)
            
            if ids_to_delete:
                self.vector_store.delete(ids_to_delete)
            
            logger.info(f"已清除数据源 {datasource_id} 的Schema")
            return True
        except Exception as e:
            logger.error(f"清除Schema失败: {e}")
            return False


# 便捷函数
def sync_schema_on_connect(
    datasource_id: int,
    schema_info: Dict[str, Any],
    db_session=None
) -> bool:
    """
    便捷函数：首次连接时同步Schema
    
    Args:
        datasource_id: 数据源ID
        schema_info: Schema信息
        db_session: 数据库会话
        
    Returns:
        是否成功
    """
    sync = SchemaSync()
    return sync.sync_on_first_connect(datasource_id, schema_info, db_session)
