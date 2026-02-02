"""
问题改写器
轻量级的问题规范化改写
"""

import re
import logging
from typing import Optional

from .time_normalizer import TimeNormalizer

logger = logging.getLogger(__name__)


class QuestionRewriter:
    """
    问题改写器
    只做轻量级的规范化，保持原意
    """
    
    # 填充词（无意义的词）
    FILLER_WORDS = [
        r'请帮我', r'请', r'帮我', r'帮我查', r'帮我找',
        r'能不能', r'能不能查', r'可以', r'可以查',
        r'我想知道', r'我想查', r'我要查',
        r'麻烦', r'麻烦你', r'麻烦查',
        r'需要', r'需要查',
        r'看看', r'看一下', r'查一下',
    ]
    
    def __init__(self, time_normalizer: Optional[TimeNormalizer] = None):
        """
        初始化问题改写器
        
        Args:
            time_normalizer: 时间标准化器
        """
        self.time_normalizer = time_normalizer or TimeNormalizer()
    
    def rewrite(self, question: str) -> str:
        """
        改写问题
        
        Args:
            question: 原始问题
            
        Returns:
            改写后的问题
        """
        if not question:
            return question
        
        result = question.strip()
        
        # 1. 去除填充词
        result = self._remove_filler_words(result)
        
        # 2. 标准化时间
        result = self.time_normalizer.normalize(result)
        
        # 3. 标准化标点
        result = self._normalize_punctuation(result)
        
        # 4. 去除多余空格
        result = re.sub(r'\s+', ' ', result).strip()
        
        logger.debug(f"问题改写: '{question}' -> '{result}'")
        return result
    
    def _remove_filler_words(self, text: str) -> str:
        """
        去除填充词
        
        Args:
            text: 输入文本
            
        Returns:
            处理后的文本
        """
        result = text
        for pattern in self.FILLER_WORDS:
            result = re.sub(pattern, '', result)
        return result.strip()
    
    def _normalize_punctuation(self, text: str) -> str:
        """
        标准化标点符号
        
        Args:
            text: 输入文本
            
        Returns:
            处理后的文本
        """
        # 统一使用中文标点
        replacements = {
            '?': '？',
            '!': '！',
            ',': '，',
            '.': '。',
            ':': '：',
            ';': '；',
            '（': '(',
            '）': ')',
        }
        
        result = text
        for old, new in replacements.items():
            result = result.replace(old, new)
        
        return result


# 全局实例
_rewriter: Optional[QuestionRewriter] = None


def get_rewriter() -> QuestionRewriter:
    """获取全局问题改写器实例"""
    global _rewriter
    if _rewriter is None:
        _rewriter = QuestionRewriter()
    return _rewriter


def rewrite_question(question: str) -> str:
    """
    便捷函数：改写问题
    
    Args:
        question: 原始问题
        
    Returns:
        改写后的问题
    """
    rewriter = get_rewriter()
    return rewriter.rewrite(question)


# 测试
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    test_cases = [
        "请帮我查一下昨天的工单量",
        "能不能帮我看看最近7天的数据？",
        "我想知道上周的回访量",
        "麻烦查一下3天前的情况",
        "需要统计12月25日的数据",
    ]
    
    rewriter = QuestionRewriter()
    for case in test_cases:
        result = rewriter.rewrite(case)
        print(f"{case}")
        print(f"  -> {result}\n")
