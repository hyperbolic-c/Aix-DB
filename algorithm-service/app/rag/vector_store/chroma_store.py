"""
ChromaDB 向量存储实现
"""

import logging
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from .base import VectorStore
from .embeddings import EmbeddingModel

logger = logging.getLogger(__name__)


class ChromaVectorStore(VectorStore):
    """
    基于 ChromaDB 的向量存储实现
    支持持久化和内存模式
    """
    
    def __init__(
        self,
        collection_name: str,
        embedding_model: Optional[EmbeddingModel] = None,
        persist_directory: Optional[str] = None,
        use_memory: bool = False
    ):
        """
        初始化 ChromaDB 向量存储
        
        Args:
            collection_name: 集合名称
            embedding_model: 嵌入模型实例
            persist_directory: 持久化目录（None则使用默认路径）
            use_memory: 是否仅使用内存（不持久化）
        """
        self.collection_name = collection_name
        self.embedding_model = embedding_model or EmbeddingModel()
        self.use_memory = use_memory
        
        # 设置持久化目录
        if persist_directory is None and not use_memory:
            persist_directory = str(
                Path(__file__).parent.parent.parent.parent / "data" / "vector_store"
            )
        self.persist_directory = persist_directory
        
        self._client = None
        self._collection = None
        
        logger.info(f"ChromaVectorStore初始化: collection={collection_name}, persist={not use_memory}")
    
    def _get_client(self):
        """懒加载 ChromaDB 客户端"""
        if self._client is not None:
            return self._client
        
        try:
            import chromadb
            from chromadb.config import Settings
            
            if self.use_memory:
                # 内存模式
                self._client = chromadb.Client()
                logger.info("ChromaDB 内存模式已启动")
            else:
                # 持久化模式
                os.makedirs(self.persist_directory, exist_ok=True)
                self._client = chromadb.PersistentClient(
                    path=self.persist_directory,
                    settings=Settings(
                        anonymized_telemetry=False,
                        allow_reset=True
                    )
                )
                logger.info(f"ChromaDB 持久化模式: {self.persist_directory}")
            
            return self._client
            
        except ImportError:
            logger.error("chromadb 未安装，请运行: pip install chromadb")
            raise
        except Exception as e:
            logger.error(f"ChromaDB 初始化失败: {e}")
            raise
    
    def _get_collection(self):
        """获取或创建集合"""
        if self._collection is not None:
            return self._collection
        
        client = self._get_client()
        
        try:
            # 尝试获取现有集合
            self._collection = client.get_collection(name=self.collection_name)
            logger.debug(f"获取现有集合: {self.collection_name}")
        except Exception:
            # 创建新集合
            self._collection = client.create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}  # 使用余弦相似度
            )
            logger.info(f"创建新集合: {self.collection_name}")
        
        return self._collection
    
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
        if not texts:
            return []
        
        collection = self._get_collection()
        
        # 生成ID
        if ids is None:
            import uuid
            ids = [str(uuid.uuid4()) for _ in texts]
        
        # 生成嵌入向量
        embeddings = self.embedding_model.embed_documents(texts)
        
        # 添加到 ChromaDB
        collection.add(
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas or [{} for _ in texts],
            ids=ids
        )
        
        logger.debug(f"添加 {len(texts)} 个文档到集合 {self.collection_name}")
        return ids
    
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
        collection = self._get_collection()
        
        # 生成查询向量
        query_embedding = self.embedding_model.embed_query(query)
        
        # 搜索
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            where=filter,
            include=["documents", "metadatas", "distances"]
        )
        
        # 格式化结果
        formatted_results = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                distance = results["distances"][0][i]
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                
                # 将距离转换为相似度分数（余弦距离 -> 余弦相似度）
                similarity = 1 - distance
                
                formatted_results.append((doc, similarity, metadata))
        
        return formatted_results
    
    def delete(self, ids: List[str]) -> bool:
        """
        删除指定ID的文档
        
        Args:
            ids: 文档ID列表
            
        Returns:
            是否成功
        """
        try:
            collection = self._get_collection()
            collection.delete(ids=ids)
            logger.debug(f"删除 {len(ids)} 个文档")
            return True
        except Exception as e:
            logger.error(f"删除文档失败: {e}")
            return False
    
    def clear(self) -> bool:
        """
        清空所有数据
        
        Returns:
            是否成功
        """
        try:
            client = self._get_client()
            client.delete_collection(name=self.collection_name)
            self._collection = None
            logger.info(f"清空集合: {self.collection_name}")
            return True
        except Exception as e:
            logger.error(f"清空集合失败: {e}")
            return False
    
    def count(self) -> int:
        """
        获取文档总数
        
        Returns:
            文档数量
        """
        try:
            collection = self._get_collection()
            return collection.count()
        except Exception:
            return 0
    
    def is_empty(self) -> bool:
        """
        检查是否为空
        
        Returns:
            是否为空
        """
        return self.count() == 0
    
    def get_collection_info(self) -> Dict[str, Any]:
        """
        获取集合信息
        
        Returns:
            集合信息字典
        """
        collection = self._get_collection()
        return {
            "name": self.collection_name,
            "count": collection.count(),
            "persist_directory": self.persist_directory,
            "embedding_dimension": self.embedding_model.get_dimension()
        }
