"""
向量精排器
对候选术语和SQL示例进行向量相似度排序
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from rag.vector_store.embeddings import EmbeddingModel

logger = logging.getLogger(__name__)


@dataclass
class RankedItem:
    """排序后的项目"""
    item: Dict[str, Any]
    score: float
    rank: int


class VectorRanker:
    """
    向量精排器
    使用嵌入模型计算查询与候选内容的相似度
    """
    
    def __init__(self, embedding_model: Optional[EmbeddingModel] = None):
        """
        初始化向量精排器
        
        Args:
            embedding_model: 嵌入模型实例
        """
        self.embedding_model = embedding_model or EmbeddingModel()
        logger.info("VectorRanker初始化完成")
    
    def rank_terminologies(
        self,
        question: str,
        candidates: List[Dict[str, Any]],
        top_k: int = 5
    ) -> List[RankedItem]:
        """
        对候选术语进行向量精排
        
        Args:
            question: 用户问题
            candidates: 候选术语列表
            top_k: 返回前k个
            
        Returns:
            排序后的术语列表
        """
        if not candidates:
            return []
        
        try:
            # 生成查询向量
            query_vector = self.embedding_model.embed_query(question)
            
            # 计算每个候选的相似度
            scored_items = []
            for candidate in candidates:
                # 构建候选文本
                candidate_text = self._build_terminology_text(candidate)
                
                # 生成候选向量
                candidate_vector = self.embedding_model.embed_query(candidate_text)
                
                # 计算余弦相似度
                similarity = self._cosine_similarity(query_vector, candidate_vector)
                
                scored_items.append((candidate, similarity))
            
            # 按相似度排序
            scored_items.sort(key=lambda x: x[1], reverse=True)
            
            # 构建结果
            ranked = []
            for i, (item, score) in enumerate(scored_items[:top_k]):
                ranked.append(RankedItem(item=item, score=score, rank=i + 1))
            
            logger.debug(f"术语精排完成: {len(ranked)} 个结果")
            return ranked
            
        except Exception as e:
            logger.error(f"术语精排失败: {e}")
            # 失败时返回原始顺序的前top_k个
            return [
                RankedItem(item=c, score=0.0, rank=i + 1)
                for i, c in enumerate(candidates[:top_k])
            ]
    
    def rank_sql_examples(
        self,
        question: str,
        candidates: List[Dict[str, Any]],
        top_k: int = 3
    ) -> List[RankedItem]:
        """
        对候选SQL示例进行向量精排
        
        Args:
            question: 用户问题
            candidates: 候选SQL示例列表
            top_k: 返回前k个
            
        Returns:
            排序后的SQL示例列表
        """
        if not candidates:
            return []
        
        try:
            # 生成查询向量
            query_vector = self.embedding_model.embed_query(question)
            
            # 计算每个候选的相似度
            scored_items = []
            for candidate in candidates:
                # 使用问题作为候选文本
                candidate_text = candidate.get("question", "")
                
                # 生成候选向量
                candidate_vector = self.embedding_model.embed_query(candidate_text)
                
                # 计算余弦相似度
                similarity = self._cosine_similarity(query_vector, candidate_vector)
                
                scored_items.append((candidate, similarity))
            
            # 按相似度排序
            scored_items.sort(key=lambda x: x[1], reverse=True)
            
            # 构建结果
            ranked = []
            for i, (item, score) in enumerate(scored_items[:top_k]):
                ranked.append(RankedItem(item=item, score=score, rank=i + 1))
            
            logger.debug(f"SQL示例精排完成: {len(ranked)} 个结果")
            return ranked
            
        except Exception as e:
            logger.error(f"SQL示例精排失败: {e}")
            # 失败时返回原始顺序的前top_k个
            return [
                RankedItem(item=c, score=0.0, rank=i + 1)
                for i, c in enumerate(candidates[:top_k])
            ]
    
    def _build_terminology_text(self, terminology: Dict[str, Any]) -> str:
        """
        构建术语的文本表示
        
        Args:
            terminology: 术语字典
            
        Returns:
            文本表示
        """
        parts = []
        
        if term := terminology.get("term"):
            parts.append(term)
        
        if description := terminology.get("description"):
            parts.append(description)
        
        if synonyms := terminology.get("synonyms", []):
            parts.extend(synonyms)
        
        return " ".join(parts)
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        计算余弦相似度
        
        Args:
            vec1: 向量1
            vec2: 向量2
            
        Returns:
            相似度分数（-1到1）
        """
        import math
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)


# 全局实例
_ranker: Optional[VectorRanker] = None


def get_ranker() -> VectorRanker:
    """获取全局向量精排器实例"""
    global _ranker
    if _ranker is None:
        _ranker = VectorRanker()
    return _ranker


def rank_candidates(
    question: str,
    terminologies: Optional[List[Dict[str, Any]]] = None,
    sql_examples: Optional[List[Dict[str, Any]]] = None,
    top_k_terms: int = 5,
    top_k_examples: int = 3
) -> Dict[str, List[RankedItem]]:
    """
    便捷函数：对候选内容进行精排
    
    Args:
        question: 用户问题
        terminologies: 候选术语列表
        sql_examples: 候选SQL示例列表
        top_k_terms: 返回术语数量
        top_k_examples: 返回示例数量
        
    Returns:
        精排结果字典
    """
    ranker = get_ranker()
    
    return {
        "terminologies": ranker.rank_terminologies(question, terminologies or [], top_k_terms),
        "sql_examples": ranker.rank_sql_examples(question, sql_examples or [], top_k_examples)
    }
