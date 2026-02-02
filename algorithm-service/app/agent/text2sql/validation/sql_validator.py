"""
SQL验证器
整合语法、语义和Schema验证
"""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

from .syntax_checker import SyntaxChecker, check_syntax
from .semantic_checker import SemanticChecker, check_semantic_match

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """验证结果"""
    valid: bool  # 是否通过验证
    passed_checks: list = field(default_factory=list)  # 通过的检查
    failed_checks: list = field(default_factory=list)  # 失败的检查
    warnings: list = field(default_factory=list)  # 警告
    score: float = 0.0  # 综合得分
    feedback: str = ""  # 反馈信息
    details: Dict[str, Any] = field(default_factory=dict)  # 详细信息


class SQLValidator:
    """
    SQL验证器
    整合多种验证方式，提供全面的SQL质量检查
    """
    
    def __init__(
        self,
        syntax_checker: Optional[SyntaxChecker] = None,
        semantic_checker: Optional[SemanticChecker] = None
    ):
        """
        初始化SQL验证器
        
        Args:
            syntax_checker: 语法检查器
            semantic_checker: 语义检查器
        """
        self.syntax_checker = syntax_checker or SyntaxChecker()
        self.semantic_checker = semantic_checker or SemanticChecker()
    
    def validate(
        self,
        question: str,
        sql: str,
        schema: Optional[Dict[str, Any]] = None,
        db_type: str = "mysql"
    ) -> ValidationResult:
        """
        验证SQL
        
        Args:
            question: 用户问题
            sql: SQL语句
            schema: 数据库Schema（可选）
            db_type: 数据库类型
            
        Returns:
            验证结果
        """
        passed = []
        failed = []
        warnings = []
        details = {}
        
        # 1. 语法检查
        syntax_result = self.syntax_checker.check(sql, db_type)
        details["syntax"] = syntax_result
        
        if syntax_result["valid"]:
            passed.append("syntax")
        else:
            failed.append({"check": "syntax", "error": syntax_result["error"]})
        
        if syntax_result.get("warnings"):
            warnings.extend(syntax_result["warnings"])
        
        # 2. 语义检查
        semantic_result = self.semantic_checker.check_match(question, sql)
        details["semantic"] = semantic_result
        
        if semantic_result.matched:
            passed.append("semantic")
        else:
            failed.append({
                "check": "semantic",
                "error": semantic_result.analysis,
                "score": semantic_result.score
            })
        
        # 3. Schema检查（如果有Schema）
        if schema:
            schema_result = self._check_schema(sql, schema)
            details["schema"] = schema_result
            
            if schema_result["valid"]:
                passed.append("schema")
            else:
                failed.append({"check": "schema", "error": schema_result["error"]})
        
        # 4. 计算综合得分
        score = self._calculate_score(
            syntax_result,
            semantic_result,
            details.get("schema")
        )
        
        # 5. 生成反馈
        feedback = self._generate_feedback(failed, warnings)
        
        # 6. 判断是否通过
        valid = len([f for f in failed if f["check"] in ["syntax", "schema"]]) == 0
        
        return ValidationResult(
            valid=valid,
            passed_checks=passed,
            failed_checks=failed,
            warnings=warnings,
            score=score,
            feedback=feedback,
            details=details
        )
    
    def _check_schema(self, sql: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        检查SQL中的表和字段是否在Schema中存在
        
        Args:
            sql: SQL语句
            schema: Schema信息
            
        Returns:
            检查结果
        """
        import re
        
        errors = []
        warnings = []
        
        # 提取SQL中的表名
        table_pattern = r'FROM\s+(\w+)|JOIN\s+(\w+)'
        tables_in_sql = set()
        for match in re.finditer(table_pattern, sql, re.IGNORECASE):
            table = match.group(1) or match.group(2)
            if table:
                tables_in_sql.add(table.lower())
        
        # 获取Schema中的表名
        schema_tables = set()
        if "tables" in schema:
            for table in schema["tables"]:
                if isinstance(table, dict):
                    schema_tables.add(table.get("name", "").lower())
                else:
                    schema_tables.add(str(table).lower())
        
        # 检查表是否存在
        for table in tables_in_sql:
            if table not in schema_tables:
                errors.append(f"表 '{table}' 在Schema中不存在")
        
        return {
            "valid": len(errors) == 0,
            "error": "; ".join(errors) if errors else None,
            "warnings": warnings,
            "tables_found": list(tables_in_sql & schema_tables),
            "tables_missing": list(tables_in_sql - schema_tables)
        }
    
    def _calculate_score(
        self,
        syntax_result: Dict,
        semantic_result,
        schema_result: Optional[Dict]
    ) -> float:
        """
        计算综合得分
        
        Args:
            syntax_result: 语法检查结果
            semantic_result: 语义检查结果
            schema_result: Schema检查结果
            
        Returns:
            得分（0-1）
        """
        scores = []
        weights = []
        
        # 语法得分（权重0.4）
        syntax_score = 1.0 if syntax_result["valid"] else 0.0
        scores.append(syntax_score)
        weights.append(0.4)
        
        # 语义得分（权重0.4）
        semantic_score = semantic_result.score
        scores.append(semantic_score)
        weights.append(0.4)
        
        # Schema得分（权重0.2）
        if schema_result:
            schema_score = 1.0 if schema_result["valid"] else 0.0
            scores.append(schema_score)
            weights.append(0.2)
        
        # 加权平均
        total_weight = sum(weights)
        weighted_score = sum(s * w for s, w in zip(scores, weights)) / total_weight
        
        return round(weighted_score, 2)
    
    def _generate_feedback(self, failed: list, warnings: list) -> str:
        """
        生成反馈信息
        
        Args:
            failed: 失败的检查
            warnings: 警告
            
        Returns:
            反馈信息
        """
        feedback_parts = []
        
        if failed:
            errors = [f["error"] for f in failed]
            feedback_parts.append(f"问题: {'; '.join(errors)}")
        
        if warnings:
            feedback_parts.append(f"警告: {'; '.join(warnings[:3])}")  # 最多显示3个警告
        
        if not failed and not warnings:
            feedback_parts.append("SQL验证通过")
        
        return " ".join(feedback_parts)


# 全局实例
_validator: Optional[SQLValidator] = None


def get_validator() -> SQLValidator:
    """获取全局SQL验证器实例"""
    global _validator
    if _validator is None:
        _validator = SQLValidator()
    return _validator


def validate_sql(
    question: str,
    sql: str,
    schema: Optional[Dict[str, Any]] = None,
    db_type: str = "mysql"
) -> ValidationResult:
    """
    便捷函数：验证SQL
    
    Args:
        question: 用户问题
        sql: SQL语句
        schema: Schema信息
        db_type: 数据库类型
        
    Returns:
        验证结果
    """
    validator = get_validator()
    return validator.validate(question, sql, schema, db_type)


# 测试
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    test_cases = [
        {
            "question": "查询昨天的工单量",
            "sql": "SELECT COUNT(*) FROM tickets WHERE created_at >= '2024-01-20'",
            "schema": {
                "tables": [
                    {"name": "tickets", "columns": ["id", "created_at"]}
                ]
            }
        },
        {
            "question": "查询用户数量",
            "sql": "SELECT * FROM users",  # 应该使用COUNT
            "schema": {
                "tables": [
                    {"name": "users", "columns": ["id", "name"]}
                ]
            }
        },
        {
            "question": "查询订单",
            "sql": "SELECT * FROM orders WHERE",  # 语法错误
            "schema": None
        }
    ]
    
    validator = SQLValidator()
    for case in test_cases:
        result = validator.validate(
            case["question"],
            case["sql"],
            case.get("schema")
        )
        print(f"\n问题: {case['question']}")
        print(f"SQL: {case['sql']}")
        print(f"验证结果:")
        print(f"  通过: {result.valid}")
        print(f"  得分: {result.score}")
        print(f"  通过的检查: {result.passed_checks}")
        print(f"  失败的检查: {[f['check'] for f in result.failed_checks]}")
        print(f"  反馈: {result.feedback}")
