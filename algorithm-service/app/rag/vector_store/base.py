"""
向量存储抽象基类
定义向量存储的标准接口
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple


class VectorStore(ABC):
    """
    向量存储抽象基类
    所有向量存储实现都需要继承此类
    """
    
    @abstractmethod
    def add_texts(
        self,
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None
    ) -> List[str]:
        """
        添加文本到向量存储
        
        Args:
            texts: 文本列表
            metadatas: 元数据列表
            ids: 自定义ID列表
            
        Returns:
            添加的文档ID列表
        """
        pass
    
    @abstractmethod
    def similarity_search(
        self,
        query: str,
        k: int = 5,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        """
        相似性搜索
        
        Args:
            query: 查询文本
            k: 返回结果数量
            filter: 过滤条件
            
        Returns:
            结果列表，每项为 (文本, 相似度分数, 元数据)
        """
        pass
    
    @abstractmethod
    def delete(self, ids: List[str]) -> bool:
        """
        删除指定ID的文档
        
        Args:
            ids: 文档ID列表
            
        Returns:
            是否成功
        """
        pass
    
    @abstractmethod
    def clear(self) -> bool:
        """
        清空所有数据
        
        Returns:
            是否成功
        """
        pass
    
    @abstractmethod
    def count(self) -> int:
        """
        获取文档总数
        
        Returns:
            文档数量
        """
        pass
    
    @abstractmethod
    def is_empty(self) -> bool:
        """
        检查是否为空
        
        Returns:
            是否为空
        """
        pass
