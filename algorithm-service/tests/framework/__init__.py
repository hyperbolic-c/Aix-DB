"""
算法测试框架核心模块

提供测试用例构建、请求生成、结果验证等功能
保持与算法内部实现解耦，兼容多个算法服务版本
"""

from .request_builder import CompetitionRequestBuilder, ExcelSchemaLoader
from .validators import ExecutionValidator, SQLSyntaxChecker

__all__ = [
    "CompetitionRequestBuilder",
    "ExcelSchemaLoader",
    "ExecutionValidator",
    "SQLSyntaxChecker",
]
