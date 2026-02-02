"""
Schema 向量化索引构建器
将数据库Schema构建为向量索引
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from rag.vector_store import ChromaVectorStore
from rag.vector_store.embeddings import EmbeddingModel

logger = logging.getLogger(__name__)


class SchemaIndexer:
    """
    Schema索引器
    将数据库Schema信息构建为向量索引，支持表级别和字段级别的索引
    """
    
    def __init__(
        self,
        vector_store: Optional[ChromaVectorStore] = None,
        embedding_model: Optional[EmbeddingModel] = None
    ):
        """
        初始化Schema索引器
        
        Args:
            vector_store: 向量存储实例
            embedding_model: 嵌入模型实例
        """
        self.vector_store = vector_store or ChromaVectorStore(
            collection_name="schema_store"
        )
        self.embedding_model = embedding_model or EmbeddingModel()
        logger.info("SchemaIndexer初始化完成")
    
    def index_from_json(
        self,
        schema_json_path: str,
        datasource_id: Optional[int] = None,
        clear_existing: bool = False
    ) -> Dict[str, int]:
        """
        从JSON文件构建Schema索引
        
        Args:
            schema_json_path: Schema JSON文件路径
            datasource_id: 数据源ID
            clear_existing: 是否清空现有索引
            
        Returns:
            统计信息字典
        """
        logger.info(f"开始构建Schema索引: {schema_json_path}")
        
        # 清空现有索引
        if clear_existing:
            self.vector_store.clear()
            logger.info("已清空现有索引")
        
        # 加载Schema
        with open(schema_json_path, 'r', encoding='utf-8') as f:
            schema_data = json.load(f)
        
        # 索引表和字段
        stats = {"tables": 0, "columns": 0}
        
        tables = schema_data.get("tables", [])
        for table in tables:
            # 索引表
            table_stats = self._index_table(table, datasource_id)
            stats["tables"] += table_stats["tables"]
            stats["columns"] += table_stats["columns"]
        
        logger.info(f"Schema索引构建完成: {stats}")
        return stats
    
    def _index_table(
        self,
        table: Dict[str, Any],
        datasource_id: Optional[int] = None
    ) -> Dict[str, int]:
        """
        索引单个表
        
        Args:
            table: 表信息字典
            datasource_id: 数据源ID
            
        Returns:
            统计信息
        """
        table_name = table.get("name", "")
        table_description = table.get("description", "")
        columns = table.get("columns", [])
        
        stats = {"tables": 0, "columns": 0}
        
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
        self.vector_store.add_texts(
            texts=[table_text],
            metadatas=[table_metadata],
            ids=[f"table_{table_name}"]
        )
        stats["tables"] += 1
        
        # 索引字段
        for column in columns:
            self._index_column(table_name, column, datasource_id)
            stats["columns"] += 1
        
        return stats
    
    def _index_column(
        self,
        table_name: str,
        column: Dict[str, Any],
        datasource_id: Optional[int] = None
    ):
        """
        索引单个字段
        
        Args:
            table_name: 表名
            column: 字段信息字典
            datasource_id: 数据源ID
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
        self.vector_store.add_texts(
            texts=[column_text],
            metadatas=[column_metadata],
            ids=[f"column_{table_name}_{column_name}"]
        )
    
    def _build_table_text(
        self,
        table_name: str,
        table_description: str,
        columns: List[Dict[str, Any]]
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
    
    def index_sql_examples(
        self,
        examples: List[Dict[str, Any]],
        datasource_type: Optional[str] = None,
        clear_existing: bool = False
    ) -> int:
        """
        索引SQL示例
        
        Args:
            examples: SQL示例列表，每项包含question和sql
            datasource_type: 数据源类型
            clear_existing: 是否清空现有索引
            
        Returns:
            索引的示例数量
        """
        logger.info(f"开始索引SQL示例: {len(examples)} 个")
        
        # 使用专门的集合
        example_store = ChromaVectorStore(collection_name="sql_example_store")
        
        if clear_existing:
            example_store.clear()
        
        texts = []
        metadatas = []
        ids = []
        
        for i, example in enumerate(examples):
            question = example.get("question", "")
            sql = example.get("sql", "")
            explanation = example.get("explanation", "")
            
            # 构建索引文本（使用问题作为索引键）
            text = question
            
            metadata = {
                "question": question,
                "sql": sql,
                "explanation": explanation,
                "datasource_type": datasource_type
            }
            
            texts.append(text)
            metadatas.append(metadata)
            ids.append(f"example_{i}")
        
        # 批量添加
        if texts:
            example_store.add_texts(texts, metadatas, ids)
        
        logger.info(f"SQL示例索引完成: {len(texts)} 个")
        return len(texts)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取索引统计信息
        
        Returns:
            统计信息字典
        """
        return self.vector_store.get_collection_info()
    
    def is_indexed(self) -> bool:
        """
        检查是否已构建索引
        
        Returns:
            是否已索引
        """
        return not self.vector_store.is_empty()


def build_schema_index(
    schema_json_path: str,
    datasource_id: Optional[int] = None,
    clear_existing: bool = False
) -> Dict[str, int]:
    """
    便捷函数：构建Schema索引
    
    Args:
        schema_json_path: Schema JSON文件路径
        datasource_id: 数据源ID
        clear_existing: 是否清空现有索引
        
    Returns:
        统计信息字典
    """
    indexer = SchemaIndexer()
    return indexer.index_from_json(schema_json_path, datasource_id, clear_existing)
