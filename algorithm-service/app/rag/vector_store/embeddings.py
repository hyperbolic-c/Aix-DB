"""
文本嵌入模型封装
支持多种嵌入模型，包括本地和在线模型
"""

import logging
import os
from typing import List, Optional

logger = logging.getLogger(__name__)


class EmbeddingModel:
    """
    文本嵌入模型封装类
    支持 sentence-transformers 和 OpenAI 等模型
    """
    
    # 默认模型配置
    DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
    CHINESE_MODEL = "shibing624/text2vec-base-chinese"
    
    def __init__(
        self,
        model_name: Optional[str] = None,
        model_path: Optional[str] = None,
        device: str = "cpu"
    ):
        """
        初始化嵌入模型
        
        Args:
            model_name: 模型名称（HuggingFace模型名）
            model_path: 本地模型路径（优先使用）
            device: 运行设备（cpu/cuda）
        """
        self.model_name = model_name or self.DEFAULT_MODEL
        self.model_path = model_path
        self.device = device
        self._model = None
        self._is_initialized = False
        
        logger.info(f"嵌入模型配置: name={self.model_name}, path={self.model_path}, device={device}")
    
    def _load_model(self):
        """懒加载模型"""
        if self._is_initialized:
            return
        
        try:
            from sentence_transformers import SentenceTransformer
            
            # 优先使用本地路径
            if self.model_path and os.path.exists(self.model_path):
                logger.info(f"从本地路径加载模型: {self.model_path}")
                self._model = SentenceTransformer(self.model_path, device=self.device)
            else:
                logger.info(f"从HuggingFace下载模型: {self.model_name}")
                self._model = SentenceTransformer(self.model_name, device=self.device)
            
            self._is_initialized = True
            logger.info("嵌入模型加载成功")
            
        except ImportError:
            logger.error("sentence-transformers 未安装，请运行: pip install sentence-transformers")
            raise
        except Exception as e:
            logger.error(f"加载嵌入模型失败: {e}")
            raise
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        将文档列表转换为向量
        
        Args:
            texts: 文本列表
            
        Returns:
            向量列表
        """
        if not texts:
            return []
        
        self._load_model()
        
        try:
            embeddings = self._model.encode(texts, show_progress_bar=False)
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"文档嵌入失败: {e}")
            raise
    
    def embed_query(self, text: str) -> List[float]:
        """
        将查询文本转换为向量
        
        Args:
            text: 查询文本
            
        Returns:
            向量
        """
        self._load_model()
        
        try:
            embedding = self._model.encode(text, show_progress_bar=False)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"查询嵌入失败: {e}")
            raise
    
    def get_dimension(self) -> int:
        """
        获取向量维度
        
        Returns:
            向量维度
        """
        self._load_model()
        return self._model.get_sentence_embedding_dimension()
    
    @classmethod
    def from_config(cls, config: dict) -> "EmbeddingModel":
        """
        从配置创建实例
        
        Args:
            config: 配置字典
            
        Returns:
            EmbeddingModel实例
        """
        return cls(
            model_name=config.get("model_name"),
            model_path=config.get("model_path"),
            device=config.get("device", "cpu")
        )


class MockEmbeddingModel:
    """
    模拟嵌入模型（用于测试）
    返回随机向量
    """
    
    def __init__(self, dimension: int = 384):
        self.dimension = dimension
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        import random
        return [[random.random() for _ in range(self.dimension)] for _ in texts]
    
    def embed_query(self, text: str) -> List[float]:
        import random
        return [random.random() for _ in range(self.dimension)]
    
    def get_dimension(self) -> int:
        return self.dimension
