"""
数据源连接器
在数据源连接时自动同步Schema到向量库
"""

import logging
from typing import Optional, Dict, Any

from rag.sync.schema_sync import SchemaSync

logger = logging.getLogger(__name__)


class DatasourceConnector:
    """
    数据源连接器
    包装数据源连接操作，在连接时自动同步Schema
    """
    
    def __init__(self):
        self.schema_sync = SchemaSync()
    
    def connect_and_sync(
        self,
        datasource_id: int,
        db_info: Dict[str, Any],
        db_session=None
    ) -> bool:
        """
        连接数据源并同步Schema
        
        Args:
            datasource_id: 数据源ID
            db_info: 数据库Schema信息
            db_session: 数据库会话
            
        Returns:
            是否成功
        """
        try:
            # 同步Schema到向量库
            success = self.schema_sync.sync_on_first_connect(
                datasource_id=datasource_id,
                schema_info=db_info,
                db_session=db_session
            )
            
            if success:
                logger.info(f"数据源 {datasource_id} 连接并同步成功")
            else:
                logger.warning(f"数据源 {datasource_id} Schema同步失败或已同步")
            
            return success
        except Exception as e:
            logger.error(f"数据源 {datasource_id} 连接同步失败: {e}")
            return False


# 全局连接器实例
_connector: Optional[DatasourceConnector] = None


def get_datasource_connector() -> DatasourceConnector:
    """获取全局数据源连接器"""
    global _connector
    if _connector is None:
        _connector = DatasourceConnector()
    return _connector


def sync_datasource_schema(
    datasource_id: int,
    db_info: Dict[str, Any],
    db_session=None
) -> bool:
    """
    便捷函数：同步数据源Schema
    
    Args:
        datasource_id: 数据源ID
        db_info: 数据库Schema信息
        db_session: 数据库会话
        
    Returns:
        是否成功
    """
    connector = get_datasource_connector()
    return connector.connect_and_sync(datasource_id, db_info, db_session)
