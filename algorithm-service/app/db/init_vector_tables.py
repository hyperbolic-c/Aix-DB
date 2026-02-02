"""
向量检索相关表初始化脚本
创建术语表、SQL示例表、Schema表
"""

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)


def init_vector_tables(db_path: str = None):
    """
    初始化向量检索相关表
    
    Args:
        db_path: 数据库路径，默认使用项目数据库
    """
    if db_path is None:
        # 默认路径
        db_path = str(Path(__file__).parent.parent.parent / "data" / "chat_history.db")
    
    logger.info(f"初始化向量检索表: {db_path}")
    
    # 读取SQL文件
    sql_file = Path(__file__).parent / "migrations" / "create_vector_tables.sql"
    with open(sql_file, 'r', encoding='utf-8') as f:
        sql_script = f.read()
    
    # 执行SQL
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(sql_script)
        conn.commit()
        logger.info("向量检索表初始化成功")
        
        # 验证表是否创建成功
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        required_tables = ['terminologies', 'training_examples', 'schemas']
        for table in required_tables:
            if table in tables:
                logger.info(f"  ✓ 表 {table} 已创建")
            else:
                logger.error(f"  ✗ 表 {table} 创建失败")
                
    except Exception as e:
        logger.error(f"初始化失败: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def check_tables_exist(db_path: str = None) -> bool:
    """
    检查向量检索表是否已存在
    
    Args:
        db_path: 数据库路径
        
    Returns:
        是否全部存在
    """
    if db_path is None:
        db_path = str(Path(__file__).parent.parent.parent / "data" / "chat_history.db")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        required_tables = ['terminologies', 'training_examples', 'schemas']
        return all(table in tables for table in required_tables)
    except Exception:
        return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_vector_tables()
