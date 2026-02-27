"""
Schema 检索器 - 基于 BM25 的表结构检索
从原实现 agent/text2sql/analysis/schema_inspector.py 迁移
"""

import re
from typing import List, Dict, Tuple, Optional


class SchemaRetriever:
    """基于 BM25 的表结构检索器
    
    原实现使用 BM25 + 向量检索，简化后只使用 BM25
    """
    
    def __init__(self, tables: List[Dict]):
        """
        Args:
            tables: 全量表结构列表，每个表包含 name, comment, columns
        """
        self.tables = {t["name"]: t for t in tables}
        self.table_names = list(self.tables.keys())
        self.bm25 = None
        self.tokenized_corpus = []
        
        if tables:
            self._build_bm25_index()
    
    def _tokenize(self, text: str) -> List[str]:
        """中文分词 - 简化版，使用字符级分词"""
        if not text:
            return []
        
        # 清理文本
        text = re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9]", " ", str(text))
        
        # 简单的字符级分词（中英文混合）
        tokens = []
        for word in text.split():
            word = word.strip()
            if not word:
                continue
            
            # 英文单词直接加入
            if re.match(r'^[a-zA-Z0-9_]+$', word):
                tokens.append(word.lower())
            else:
                # 中文逐字符分词
                for char in word:
                    if char.strip():
                        tokens.append(char)
        
        return tokens
    
    def _build_document(self, table: Dict) -> str:
        """构建检索文档 - 合并表名、注释、字段信息"""
        parts = []
        
        # 表名
        parts.append(table.get("name", ""))
        
        # 表注释
        if table.get("comment"):
            parts.append(table["comment"])
        
        # 字段信息
        for col in table.get("columns", []):
            parts.append(col.get("name", ""))
            if col.get("comment"):
                parts.append(col["comment"])
        
        return " ".join(parts)
    
    def _build_bm25_index(self):
        """构建 BM25 索引"""
        try:
            from rank_bm25 import BM25Okapi
            
            corpus = [self._build_document(self.tables[name]) for name in self.table_names]
            self.tokenized_corpus = [self._tokenize(doc) for doc in corpus]
            
            if self.tokenized_corpus:
                self.bm25 = BM25Okapi(self.tokenized_corpus)
        except ImportError:
            # 如果没有 rank_bm25，使用简单匹配
            self.bm25 = None
    
    def retrieve(self, query: str, top_k: int = 6) -> Tuple[List[str], List[str]]:
        """检索相关表
        
        Args:
            query: 用户查询
            top_k: 返回表数量
            
        Returns:
            (检索到的表名列表, 分词结果)
        """
        tokens = self._tokenize(query)
        
        if not self.bm25 or not self.table_names:
            return [], tokens
        
        # BM25 评分
        scores = self.bm25.get_scores(tokens)
        
        # 排序并取 top_k
        scored_tables = list(enumerate(scores))
        scored_tables.sort(key=lambda x: x[1], reverse=True)
        
        result = [self.table_names[idx] for idx, _ in scored_tables[:top_k]]
        return result, tokens
    
    def get_table_info(self, table_names: List[str]) -> List[Dict]:
        """获取指定表的详细信息"""
        return [self.tables[name] for name in table_names if name in self.tables]
    
    def get_all_tables(self) -> List[Dict]:
        """获取所有表"""
        return list(self.tables.values())


class SimpleSchemaRetriever(SchemaRetriever):
    """简化版 Schema 检索器（无 BM25 依赖）
    
    使用简单的关键词匹配，适用于没有 rank_bm25 的环境
    """
    
    def _build_bm25_index(self):
        """不构建 BM25 索引"""
        self.bm25 = None
        corpus = [self._build_document(self.tables[name]) for name in self.table_names]
        self.tokenized_corpus = [self._tokenize(doc) for doc in corpus]
    
    def retrieve(self, query: str, top_k: int = 6) -> Tuple[List[str], List[str]]:
        """使用简单关键词匹配检索"""
        tokens = self._tokenize(query)
        
        if not self.table_names:
            return [], tokens
        
        # 简单匹配评分
        scores = []
        query_tokens = set(tokens)
        
        for doc_tokens in self.tokenized_corpus:
            doc_set = set(doc_tokens)
            # 计算交集大小
            intersection = query_tokens & doc_set
            score = len(intersection)
            scores.append(score)
        
        # 排序并取 top_k
        scored_tables = list(enumerate(scores))
        scored_tables.sort(key=lambda x: x[1], reverse=True)
        
        result = [self.table_names[idx] for idx, _ in scored_tables[:top_k] if scores[idx] > 0]
        
        # 如果没有匹配，返回前 top_k 个表
        if not result and self.table_names:
            result = self.table_names[:min(top_k, len(self.table_names))]
        
        return result, tokens
