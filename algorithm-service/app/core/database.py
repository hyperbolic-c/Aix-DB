"""
数据库执行器模块
支持SQLite数据库连接和SQL执行
"""

import sqlite3
import json
import logging
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """SQL执行结果"""
    success: bool
    row_count: int = 0
    columns: List[str] = None
    rows: List[List[Any]] = None
    error: Optional[str] = None
    execution_time_ms: int = 0
    
    def __post_init__(self):
        if self.columns is None:
            self.columns = []
        if self.rows is None:
            self.rows = []
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "success": self.success,
            "row_count": self.row_count,
            "columns": self.columns,
            "rows": self.rows,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms
        }


class SchemaLoader:
    """
    Schema加载器
    从JSON文件加载完整的Schema信息
    """
    
    _schema_cache = None
    
    @classmethod
    def load_schema(cls, schema_file: Optional[str] = None) -> Dict[str, Any]:
        """
        加载Schema信息
        
        Args:
            schema_file: Schema文件路径，默认使用data/schema_from_excel.json
            
        Returns:
            Schema字典
        """
        if cls._schema_cache is not None:
            return cls._schema_cache
        
        if schema_file is None:
            # 默认从Excel生成的Schema文件
            # 从app/core/database.py -> algorithm-service/data/schema_from_excel.json
            schema_file = Path(__file__).parent.parent.parent / "data" / "schema_from_excel.json"
        
        try:
            with open(schema_file, 'r', encoding='utf-8') as f:
                cls._schema_cache = json.load(f)
            logger.info(f"Schema加载成功: {schema_file}")
            return cls._schema_cache
        except FileNotFoundError:
            logger.warning(f"Schema文件不存在: {schema_file}，将从数据库提取")
            return None
        except Exception as e:
            logger.error(f"Schema加载失败: {e}")
            return None
    
    @classmethod
    def get_table_info(cls, table_name: str, schema: Dict = None) -> Optional[Dict]:
        """
        获取表信息
        
        Args:
            table_name: 表名
            schema: Schema字典，如果为None则使用缓存
            
        Returns:
            表信息字典
        """
        if schema is None:
            schema = cls.load_schema()
        
        if schema is None:
            return None
        
        for table in schema.get("tables", []):
            if table["name"] == table_name:
                return table
        return None
    
    @classmethod
    def get_field_info(cls, table_name: str, field_name: str, schema: Dict = None) -> Optional[Dict]:
        """
        获取字段信息
        
        Args:
            table_name: 表名
            field_name: 字段名
            schema: Schema字典，如果为None则使用缓存
            
        Returns:
            字段信息字典
        """
        table_info = cls.get_table_info(table_name, schema)
        if table_info is None:
            return None
        
        for field in table_info.get("fields", []):
            if field["name"] == field_name:
                return field
        return None


class SQLiteExecutor:
    """
    SQLite数据库执行器
    用于连接SQLite数据库并执行SQL查询
    """
    
    def __init__(self, db_path: str):
        """
        初始化SQLite执行器
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self._schema = None
        logger.info(f"初始化SQLite执行器，数据库路径: {db_path}")
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def execute(self, sql: str, params: tuple = ()) -> ExecutionResult:
        """
        执行SQL查询
        
        Args:
            sql: SQL语句
            params: 查询参数
            
        Returns:
            执行结果
        """
        start_time = time.time()
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, params)
                
                # 获取列名
                columns = [description[0] for description in cursor.description] if cursor.description else []
                
                # 获取所有行
                rows = cursor.fetchall()
                rows = [list(row) for row in rows]
                
                execution_time = int((time.time() - start_time) * 1000)
                
                logger.info(f"SQL执行成功，返回 {len(rows)} 行，耗时 {execution_time}ms")
                
                return ExecutionResult(
                    success=True,
                    row_count=len(rows),
                    columns=columns,
                    rows=rows,
                    execution_time_ms=execution_time
                )
                
        except Exception as e:
            execution_time = int((time.time() - start_time) * 1000)
            logger.error(f"SQL执行错误: {e}")
            return ExecutionResult(
                success=False,
                error=str(e),
                execution_time_ms=execution_time
            )
    
    def get_schema_info(self) -> Dict[str, Any]:
        """
        获取数据库Schema信息
        优先从Excel加载，如果不存在则从数据库提取
        
        Returns:
            Schema信息字典
        """
        # 首先尝试从Excel加载Schema
        excel_schema = SchemaLoader.load_schema()
        if excel_schema is not None:
            logger.info(f"使用Excel Schema，共 {len(excel_schema.get('tables', []))} 张表")
            return excel_schema
        
        # 如果Excel Schema不存在，从数据库提取
        logger.info("从数据库提取Schema信息")
        schema = {
            "database": "final",
            "db_type": "sqlite",
            "tables": []
        }
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 获取所有表
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name != 'sqlite_sequence'")
                tables = cursor.fetchall()
                
                for (table_name,) in tables:
                    # 从Excel Schema获取表信息
                    table_info = SchemaLoader.get_table_info(table_name)
                    
                    if table_info:
                        # 使用Excel中的表信息（包含注释）
                        schema["tables"].append(table_info)
                    else:
                        # 从数据库提取表信息
                        cursor.execute(f"PRAGMA table_info({table_name})")
                        columns = cursor.fetchall()
                        
                        fields = []
                        for col in columns:
                            field_name = col[1]
                            field_type = col[2]
                            
                            # 尝试从Excel获取字段注释
                            field_info = SchemaLoader.get_field_info(table_name, field_name)
                            field_comment = field_info.get("comment", "") if field_info else ""
                            
                            fields.append({
                                "name": field_name,
                                "type": field_type,
                                "comment": field_comment
                            })
                        
                        schema["tables"].append({
                            "name": table_name,
                            "comment": "",
                            "fields": fields
                        })
                
                logger.info(f"Schema提取完成，共 {len(schema['tables'])} 张表")
                return schema
                
        except Exception as e:
            logger.error(f"Schema提取失败: {e}")
            return schema
    
    def test_connection(self) -> bool:
        """
        测试数据库连接
        
        Returns:
            是否连接成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                return True
        except Exception as e:
            logger.error(f"数据库连接测试失败: {e}")
            return False


class DatabaseExecutorFactory:
    """
    数据库执行器工厂
    根据数据库类型创建对应的执行器
    """
    
    @staticmethod
    def create_executor(db_type: str, config: Dict[str, Any]) -> SQLiteExecutor:
        """
        创建数据库执行器
        
        Args:
            db_type: 数据库类型（sqlite, mysql, postgresql等）
            config: 数据库配置
            
        Returns:
            数据库执行器实例
        """
        db_type = db_type.lower()
        
        if db_type in ['sqlite', 'sqlite3']:
            db_path = config.get('db_path', config.get('database', ''))
            return SQLiteExecutor(db_path)
        else:
            raise ValueError(f"不支持的数据库类型: {db_type}")


# 便捷函数
def get_sqlite_executor(db_path: str) -> SQLiteExecutor:
    """
    获取SQLite执行器
    
    Args:
        db_path: 数据库路径
        
    Returns:
        SQLite执行器
    """
    return SQLiteExecutor(db_path)
