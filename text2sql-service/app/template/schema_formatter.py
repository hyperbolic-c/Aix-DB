"""
Schema 格式化工具
将表结构格式化为 M-Schema 格式
从原实现 agent/text2sql/template/prompt_builder.py 迁移
"""

from typing import Dict, List, Any


def format_schema_to_m_schema(
    db_info: Dict[str, Any],
    db_name: str = "database",
    db_type: str = "mysql"
) -> str:
    """将表结构格式化为 M-Schema 格式
    
    Args:
        db_info: 表结构信息，格式为 {table_name: table_info}
        db_name: 数据库名
        db_type: 数据库类型
        
    Returns:
        M-Schema 格式的字符串
    """
    lines = []
    lines.append(f"【DB_ID】 {db_name}")
    lines.append("【Schema】")
    lines.append("")
    
    for table_name, table_info in db_info.items():
        table_comment = table_info.get("comment", "")
        comment_str = f", {table_comment}" if table_comment else ""
        lines.append(f"# Table: {table_name}{comment_str}")
        lines.append("[")
        
        for col in table_info.get("columns", []):
            col_name = col.get("name", "")
            col_type = col.get("type", "")
            col_comment = col.get("comment", "")
            is_primary = col.get("is_primary", False)
            
            # 构建字段描述
            parts = [f"({col_name}: {col_type}"]
            
            if is_primary:
                parts.append("Primary key")
            
            if col_comment:
                parts.append(col_comment)
            
            parts.append(")")
            lines.append(", ".join(parts))
        
        lines.append("]")
        lines.append("")
    
    return "\n".join(lines)


def get_database_engine_info(db_type: str) -> str:
    """获取数据库引擎信息
    
    Args:
        db_type: 数据库类型
        
    Returns:
        数据库引擎描述字符串
    """
    engine_map = {
        "mysql": "MySQL 8.0",
        "postgresql": "PostgreSQL 14",
        "postgres": "PostgreSQL 14",
        "oracle": "Oracle 19c",
        "sqlserver": "SQL Server 2019",
        "sqlite": "SQLite 3",
        "clickhouse": "ClickHouse",
        "doris": "Apache Doris",
        "starrocks": "StarRocks",
    }
    
    return engine_map.get(db_type.lower(), f"{db_type}")


def build_terminologies_section(terminologies: str) -> str:
    """构建术语部分
    
    Args:
        terminologies: 术语文本
        
    Returns:
        格式化的术语部分
    """
    if not terminologies:
        return ""
    
    return f"""<terminologies>
{terminologies}
</terminologies>"""


def build_training_examples_section(training_examples: str) -> str:
    """构建训练示例部分
    
    Args:
        training_examples: 训练示例文本
        
    Returns:
        格式化的训练示例部分
    """
    if not training_examples:
        return ""
    
    return f"""<sql-examples>
{training_examples}
</sql-examples>"""
