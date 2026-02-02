"""
时间标准化模块
将自然语言时间表达式转换为标准日期格式
"""

import re
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class TimeNormalizer:
    """
    时间标准化器
    将相对时间（昨天、上周等）转换为绝对日期
    """
    
    # 相对时间模式
    RELATIVE_PATTERNS = {
        # 今天
        r'今天|今日|这天': 0,
        # 昨天
        r'昨天|昨日|上一天': -1,
        # 前天
        r'前天|前日': -2,
        # 明天
        r'明天|明日': 1,
        # 上周
        r'上周|上星期|上个星期': -7,
        # 本周
        r'本周|这星期|本星期': 0,
        # 最近7天
        r'最近7天|近7天|近一周|最近一周': -7,
        # 最近30天
        r'最近30天|近30天|近一个月|最近一个月': -30,
        # 上个月
        r'上个月|上月': -30,  # 简化处理
        # 本月
        r'本月|这个月': 0,
    }
    
    # 日期格式模式
    DATE_PATTERNS = [
        (r'(\d{4})年(\d{1,2})月(\d{1,2})日', '%Y-%m-%d'),
        (r'(\d{4})-(\d{1,2})-(\d{1,2})', '%Y-%m-%d'),
        (r'(\d{4})/(\d{1,2})/(\d{1,2})', '%Y-%m-%d'),
        (r'(\d{1,2})月(\d{1,2})日', 'current_year'),  # 需要补充年份
    ]
    
    def __init__(self, reference_date: Optional[datetime] = None):
        """
        初始化时间标准化器
        
        Args:
            reference_date: 参考日期，默认为当前时间
        """
        self.reference_date = reference_date or datetime.now()
    
    def normalize(self, text: str) -> str:
        """
        标准化文本中的时间表达式
        
        Args:
            text: 输入文本
            
        Returns:
            标准化后的文本
        """
        result = text
        
        # 1. 处理相对时间
        for pattern, days_offset in self.RELATIVE_PATTERNS.items():
            if re.search(pattern, result):
                target_date = self.reference_date + timedelta(days=days_offset)
                date_str = target_date.strftime('%Y-%m-%d')
                result = re.sub(pattern, date_str, result)
                logger.debug(f"时间标准化: {pattern} -> {date_str}")
        
        # 2. 处理"X天前"
        result = self._normalize_days_ago(result)
        
        # 3. 处理"X月X日"（补充年份）
        result = self._normalize_month_day(result)
        
        return result
    
    def _normalize_days_ago(self, text: str) -> str:
        """
        处理"X天前"格式
        
        Args:
            text: 输入文本
            
        Returns:
            标准化后的文本
        """
        pattern = r'(\d+)天前'
        
        def replace_days_ago(match):
            days = int(match.group(1))
            target_date = self.reference_date - timedelta(days=days)
            return target_date.strftime('%Y-%m-%d')
        
        return re.sub(pattern, replace_days_ago, text)
    
    def _normalize_month_day(self, text: str) -> str:
        """
        处理"X月X日"格式，补充年份
        
        Args:
            text: 输入文本
            
        Returns:
            标准化后的文本
        """
        pattern = r'(\d{1,2})月(\d{1,2})日'
        
        def replace_month_day(match):
            month = int(match.group(1))
            day = int(match.group(2))
            year = self.reference_date.year
            
            # 如果月份大于当前月，可能是去年的日期
            if month > self.reference_date.month:
                year -= 1
            
            return f"{year}-{month:02d}-{day:02d}"
        
        return re.sub(pattern, replace_month_day, text)
    
    def extract_date_range(self, text: str) -> Optional[Tuple[str, str]]:
        """
        提取日期范围
        
        Args:
            text: 输入文本
            
        Returns:
            (开始日期, 结束日期) 或 None
        """
        # 处理"X到Y"、"X至Y"格式
        range_pattern = r'(\d{4}-\d{2}-\d{2})\s*到|至\s*(\d{4}-\d{2}-\d{2})'
        match = re.search(range_pattern, text)
        if match:
            return (match.group(1), match.group(2))
        
        # 处理"最近X天"
        recent_pattern = r'最近(\d+)天|近(\d+)天'
        match = re.search(recent_pattern, text)
        if match:
            days = int(match.group(1) or match.group(2))
            end_date = self.reference_date
            start_date = end_date - timedelta(days=days)
            return (
                start_date.strftime('%Y-%m-%d'),
                end_date.strftime('%Y-%m-%d')
            )
        
        return None


# 全局实例
_normalizer: Optional[TimeNormalizer] = None


def get_normalizer() -> TimeNormalizer:
    """获取全局时间标准化器实例"""
    global _normalizer
    if _normalizer is None:
        _normalizer = TimeNormalizer()
    return _normalizer


def normalize_time(text: str, reference_date: Optional[datetime] = None) -> str:
    """
    便捷函数：标准化时间表达式
    
    Args:
        text: 输入文本
        reference_date: 参考日期
        
    Returns:
        标准化后的文本
    """
    if reference_date:
        normalizer = TimeNormalizer(reference_date)
    else:
        normalizer = get_normalizer()
    return normalizer.normalize(text)


# 测试
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    test_cases = [
        "查询昨天的工单量",
        "统计上周的数据",
        "最近7天的回访量",
        "3天前的情况",
        "12月25日的数据",
        "查询2024年1月21日的工单",
    ]
    
    normalizer = TimeNormalizer()
    for case in test_cases:
        result = normalizer.normalize(case)
        print(f"{case} -> {result}")
