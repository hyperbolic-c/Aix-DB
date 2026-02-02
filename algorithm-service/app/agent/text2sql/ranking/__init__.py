"""
向量精排模块
对后端发送的候选内容进行向量相似度精排
"""

from .vector_ranker import VectorRanker, rank_candidates

__all__ = ["VectorRanker", "rank_candidates"]
