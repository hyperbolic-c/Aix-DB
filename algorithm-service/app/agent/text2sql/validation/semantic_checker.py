"""
SQL语义检查器
检查SQL语句与用户问题的语义匹配度
"""

import logging
import re
from typing import Dict, Any, Optional
from dataclasses import dataclass

from rag.vector_store.embeddings import EmbeddingModel

logger = logging.getLogger(__name__)


@dataclass
class SemanticMatchResult:
    """语义匹配结果"""
    score: float  # 0-1分数
    matched: bool  # 是否匹配
    analysis: str  # 分析说明
    details: Dict[str, Any]  # 详细信息


class SemanticChecker:
    """
    语义检查器
    检查SQL语句是否匹配用户问题的意图
    """
    
    def __init__(self, embedding_model: Optional[EmbeddingModel] = None):
        """
        初始化语义检查器
        
        Args:
            embedding_model: 嵌入模型
        """
        self.embedding_model = embedding_model or EmbeddingModel()
    
    def check_match(
        self,
        question: str,
        sql: str,
        threshold: float = 0.6
    ) -> SemanticMatchResult:
        """
        检查问题和SQL的语义匹配度
        
        Args:
            question: 用户问题
            sql: SQL语句
            threshold: 匹配阈值
            
        Returns:
            匹配结果
        """
        if not question or not sql:
            return SemanticMatchResult(
                score=0.0,
                matched=False,
                analysis="问题或SQL为空",
                details={}
            )
        
        try:
            # 1. 提取SQL的意图描述
            sql_intent = self._extract_sql_intent(sql)
            
            # 2. 计算语义相似度
            question_vec = self.embedding_model.embed_query(question)
            intent_vec = self.embedding_model.embed_query(sql_intent)
            similarity = self._cosine_similarity(question_vec, intent_vec)
            
            # 3. 检查关键要素匹配
            element_match = self._check_element_match(question, sql)
            
            # 4. 综合评分
            final_score = similarity * 0.7 + element_match["score"] * 0.3
            
            # 5. 生成分析
            if final_score >= threshold:
                analysis = f"语义匹配良好（分数: {final_score:.2f}）"
            else:
                analysis = f"语义匹配度较低（分数: {final_score:.2f}），可能原因: {element_match['reason']}"
            
            return SemanticMatchResult(
                score=final_score,
                matched=final_score >= threshold,
                analysis=analysis,
                details={
                    "semantic_similarity": similarity,
                    "element_match": element_match,
                    "sql_intent": sql_intent
                }
            )
            
        except Exception as e:
            logger.error(f"语义检查失败: {e}")
            return SemanticMatchResult(
                score=0.0,
                matched=False,
                analysis=f"检查失败: {str(e)}",
                details={}
            )
    
    def _extract_sql_intent(self, sql: str) -> str:
        """
        提取SQL的意图描述
        
        Args:
            sql: SQL语句
            
        Returns:
            意图描述
        """
        sql_upper = sql.upper().strip()
        intent_parts = []
        
        # 判断操作类型
        if sql_upper.startswith("SELECT"):
            intent_parts.append("查询")
            
            # 提取查询内容
            select_match = re.search(r'SELECT\s+(.+?)\s+FROM', sql_upper, re.IGNORECASE)
            if select_match:
                select_part = select_match.group(1).strip()
                if select_part == "*":
                    intent_parts.append("所有字段")
                elif "COUNT" in select_part:
                    intent_parts.append("数量")
                elif "SUM" in select_part:
                    intent_parts.append("总和")
                elif "AVG" in select_part:
                    intent_parts.append("平均值")
                else:
                    intent_parts.append("特定字段")
        
        elif sql_upper.startswith("INSERT"):
            intent_parts.append("插入数据")
        
        elif sql_upper.startswith("UPDATE"):
            intent_parts.append("更新数据")
        
        elif sql_upper.startswith("DELETE"):
            intent_parts.append("删除数据")
        
        # 提取表名
        from_match = re.search(r'FROM\s+(\w+)', sql_upper, re.IGNORECASE)
        if from_match:
            intent_parts.append(f"从表{from_match.group(1)}")
        
        # 提取条件
        if "WHERE" in sql_upper:
            intent_parts.append("带条件")
        
        # 提取聚合
        if "GROUP BY" in sql_upper:
            intent_parts.append("分组")
        
        if "ORDER BY" in sql_upper:
            intent_parts.append("排序")
        
        return "，".join(intent_parts) if intent_parts else "未知操作"
    
    def _check_element_match(self, question: str, sql: str) -> Dict[str, Any]:
        """
        检查关键要素匹配
        
        Args:
            question: 用户问题
            sql: SQL语句
            
        Returns:
            匹配结果
        """
        score = 0.0
        reasons = []
        
        question_lower = question.lower()
        sql_lower = sql.lower()
        
        # 1. 检查时间相关
        time_keywords = ['今天', '昨天', '最近', '上周', '本月', '2024', '2023']
        has_time_in_question = any(kw in question for kw in time_keywords)
        has_time_in_sql = 'date' in sql_lower or 'time' in sql_lower or any(
            str(year) in sql for year in range(2020, 2030)
        )
        
        if has_time_in_question and has_time_in_sql:
            score += 0.3
        elif has_time_in_question and not has_time_in_sql:
            score -= 0.2
            reasons.append("问题提到时间但SQL没有时间条件")
        
        # 2. 检查数量相关
        quantity_keywords = ['多少', '数量', '统计', 'count']
        has_quantity = any(kw in question_lower for kw in quantity_keywords)
        has_count = 'count(' in sql_lower
        
        if has_quantity and has_count:
            score += 0.3
        elif has_quantity and not has_count:
            score -= 0.1
            reasons.append("问题询问数量但SQL没有COUNT")
        
        # 3. 检查分组相关
        group_keywords = ['各', '每个', '按', '分组']
        has_group = any(kw in question for kw in group_keywords)
        has_group_by = 'group by' in sql_lower
        
        if has_group and has_group_by:
            score += 0.2
        elif has_group and not has_group_by:
            score -= 0.1
            reasons.append("问题提到分组但SQL没有GROUP BY")
        
        # 4. 检查排序相关
        order_keywords = ['最高', '最低', '最多', '最少', '排名', '前']
        has_order = any(kw in question for kw in order_keywords)
        has_order_by = 'order by' in sql_lower
        
        if has_order and has_order_by:
            score += 0.2
        elif has_order and not has_order_by:
            score -= 0.1
            reasons.append("问题提到排序但SQL没有ORDER BY")
        
        # 确保分数在0-1之间
        score = max(0.0, min(1.0, score + 0.5))
        
        return {
            "score": score,
            "reason": "; ".join(reasons) if reasons else "关键要素匹配良好"
        }
    
    def _cosine_similarity(self, vec1, vec2) -> float:
        """计算余弦相似度"""
        import math
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)


# 全局实例
_checker: Optional[SemanticChecker] = None


def get_checker() -> SemanticChecker:
    """获取全局语义检查器实例"""
    global _checker
    if _checker is None:
        _checker = SemanticChecker()
    return _checker


def check_semantic_match(
    question: str,
    sql: str,
    threshold: float = 0.6
) -> SemanticMatchResult:
    """
    便捷函数：检查语义匹配
    
    Args:
        question: 用户问题
        sql: SQL语句
        threshold: 匹配阈值
        
    Returns:
        匹配结果
    """
    checker = get_checker()
    return checker.check_match(question, sql, threshold)
