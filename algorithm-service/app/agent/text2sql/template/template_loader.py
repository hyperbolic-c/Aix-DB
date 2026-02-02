"""
YAML 模板加载器
支持缓存机制，提高性能
"""

import logging
import yaml
from functools import cache
from pathlib import Path
from typing import Dict, Any, Union

logger = logging.getLogger(__name__)

# 基础路径配置
TEMPLATE_DIR = Path(__file__).parent / "yaml"
BASE_TEMPLATE_PATH = TEMPLATE_DIR / "template.yaml"
SQL_TEMPLATES_DIR = TEMPLATE_DIR / "sql_examples"

# 数据库类型到模板文件名的映射
DB_TYPE_TO_TEMPLATE_NAME = {
    "postgresql": "PostgreSQL",
    "pg": "PostgreSQL",
    "mysql": "MySQL",
    "oracle": "Oracle",
    "sqlserver": "Microsoft_SQL_Server",
    "mssql": "Microsoft_SQL_Server",
    "clickhouse": "ClickHouse",
    "ck": "ClickHouse",
    "redshift": "AWS_Redshift",
    "elasticsearch": "Elasticsearch",
    "es": "Elasticsearch",
    "starrocks": "StarRocks",
    "doris": "Doris",
    "dm": "DM",
    "kingbase": "Kingbase",
    "sqlite": "SQLite",
    "sqlite3": "SQLite",
    "excel": "PostgreSQL",  # Excel 使用 PostgreSQL 规则
}


@cache
def _load_template_file(file_path: Path) -> Dict[str, Any]:
    """
    内部函数：加载并解析YAML文件（带缓存）
    
    Args:
        file_path: YAML 文件路径
        
    Returns:
        解析后的字典
        
    Raises:
        FileNotFoundError: 文件不存在
        ValueError: YAML 解析错误
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Template file not found at {file_path}")
    except yaml.YAMLError as e:
        raise ValueError(f"Error parsing YAML file {file_path}: {e}")


class TemplateLoader:
    """
    YAML 模板加载器，支持缓存机制
    """
    
    @staticmethod
    def load_base_template() -> Dict[str, Any]:
        """
        获取基础模板（自动缓存）
        
        Returns:
            基础模板字典，包含所有模板模块
        """
        return _load_template_file(BASE_TEMPLATE_PATH)
    
    @staticmethod
    def load_sql_template(db_type: Union[str, None] = None) -> Dict[str, Any]:
        """
        获取数据库特定的 SQL 模板
        
        Args:
            db_type: 数据库类型（如 'postgresql', 'mysql' 等）
                    如果为 None 或找不到匹配，默认使用 PostgreSQL
        
        Returns:
            数据库特定的 SQL 模板字典
        """
        if not db_type:
            db_type = "postgresql"
        
        # 转换为小写进行匹配
        db_type_lower = db_type.lower()
        
        # 获取模板文件名
        template_name = DB_TYPE_TO_TEMPLATE_NAME.get(db_type_lower, "PostgreSQL")
        
        # 构建模板文件路径
        template_path = SQL_TEMPLATES_DIR / f"{template_name}.yaml"
        
        # 如果文件不存在，使用默认的 PostgreSQL
        if not template_path.exists():
            logger.warning(f"SQL template not found for {db_type}, using PostgreSQL as default")
            template_path = SQL_TEMPLATES_DIR / "PostgreSQL.yaml"
        
        return _load_template_file(template_path)
    
    @staticmethod
    def reload_all_templates():
        """
        清空所有模板缓存（用于开发时重新加载模板）
        """
        _load_template_file.cache_clear()
        logger.info("All template caches cleared")
    
    @staticmethod
    def get_all_sql_template_names() -> list:
        """
        获取所有支持的数据库模板名称列表
        
        Returns:
            模板名称列表
        """
        return list(set(DB_TYPE_TO_TEMPLATE_NAME.values()))
