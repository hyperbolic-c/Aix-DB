"""
SQL语法检查器
检查SQL语句的语法正确性
"""

import logging
import re
from typing import Optional, List

logger = logging.getLogger(__name__)


class SyntaxChecker:
    """
    SQL语法检查器
    使用简单的正则和规则检查SQL语法
    """
    
    # 基本的SQL关键字
    SQL_KEYWORDS = [
        'SELECT', 'FROM', 'WHERE', 'INSERT', 'UPDATE', 'DELETE',
        'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER', 'ON',
        'GROUP', 'BY', 'ORDER', 'HAVING', 'LIMIT', 'OFFSET',
        'AND', 'OR', 'NOT', 'IN', 'EXISTS', 'BETWEEN', 'LIKE',
        'COUNT', 'SUM', 'AVG', 'MAX', 'MIN', 'AS', 'DISTINCT'
    ]
    
    def __init__(self):
        """初始化语法检查器"""
        pass
    
    def check(self, sql: str, db_type: str = "mysql") -> dict:
        """
        检查SQL语法
        
        Args:
            sql: SQL语句
            db_type: 数据库类型
            
        Returns:
            检查结果字典
        """
        if not sql or not sql.strip():
            return {
                "valid": False,
                "error": "SQL语句为空",
                "details": []
            }
        
        sql = sql.strip()
        errors = []
        warnings = []
        
        # 1. 基本结构检查
        structure_check = self._check_basic_structure(sql)
        if not structure_check["valid"]:
            errors.extend(structure_check["errors"])
        warnings.extend(structure_check.get("warnings", []))
        
        # 2. 括号匹配检查
        if not self._check_parentheses(sql):
            errors.append("括号不匹配")
        
        # 3. 引号匹配检查
        quote_check = self._check_quotes(sql)
        if not quote_check["valid"]:
            errors.extend(quote_check["errors"])
        
        # 4. 关键字检查
        keyword_check = self._check_keywords(sql)
        warnings.extend(keyword_check.get("warnings", []))
        
        # 5. 特定数据库检查
        if db_type == "mysql":
            mysql_check = self._check_mysql_specific(sql)
            warnings.extend(mysql_check.get("warnings", []))
        
        return {
            "valid": len(errors) == 0,
            "error": "; ".join(errors) if errors else None,
            "warnings": warnings,
            "details": {
                "structure_ok": len([e for e in errors if "结构" in e]) == 0,
                "parentheses_ok": "括号" not in " ".join(errors),
                "quotes_ok": len([e for e in errors if "引号" in e]) == 0
            }
        }
    
    def _check_basic_structure(self, sql: str) -> dict:
        """
        检查基本SQL结构
        
        Args:
            sql: SQL语句
            
        Returns:
            检查结果
        """
        errors = []
        warnings = []
        
        sql_upper = sql.upper().strip()
        
        # 检查是否有基本的SQL命令
        has_select = sql_upper.startswith('SELECT')
        has_insert = sql_upper.startswith('INSERT')
        has_update = sql_upper.startswith('UPDATE')
        has_delete = sql_upper.startswith('DELETE')
        
        if not any([has_select, has_insert, has_update, has_delete]):
            errors.append("SQL语句必须以SELECT、INSERT、UPDATE或DELETE开头")
        
        # SELECT语句检查
        if has_select:
            # 检查是否有FROM
            if 'FROM' not in sql_upper:
                warnings.append("SELECT语句缺少FROM子句")
            
            # 检查SELECT和FROM的顺序
            select_pos = sql_upper.find('SELECT')
            from_pos = sql_upper.find('FROM')
            if from_pos > 0 and from_pos < select_pos:
                errors.append("FROM子句不能在SELECT之前")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    def _check_parentheses(self, sql: str) -> bool:
        """
        检查括号是否匹配
        
        Args:
            sql: SQL语句
            
        Returns:
            是否匹配
        """
        stack = []
        in_string = False
        string_char = None
        
        for char in sql:
            # 处理字符串
            if char in ("'", '"', '`'):
                if not in_string:
                    in_string = True
                    string_char = char
                elif char == string_char:
                    in_string = False
                    string_char = None
                continue
            
            if in_string:
                continue
            
            # 检查括号
            if char == '(':
                stack.append(char)
            elif char == ')':
                if not stack:
                    return False
                stack.pop()
        
        return len(stack) == 0
    
    def _check_quotes(self, sql: str) -> dict:
        """
        检查引号是否匹配
        
        Args:
            sql: SQL语句
            
        Returns:
            检查结果
        """
        errors = []
        
        # 检查单引号
        single_quotes = sql.count("'")
        if single_quotes % 2 != 0:
            errors.append("单引号不匹配")
        
        # 检查双引号（在某些数据库中用于标识符）
        double_quotes = sql.count('"')
        if double_quotes % 2 != 0:
            errors.append("双引号不匹配")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    def _check_keywords(self, sql: str) -> dict:
        """
        检查关键字使用
        
        Args:
            sql: SQL语句
            
        Returns:
            检查结果
        """
        warnings = []
        sql_upper = sql.upper()
        
        # 检查是否有危险操作
        if 'DROP' in sql_upper and 'TABLE' in sql_upper:
            warnings.append("SQL包含DROP TABLE操作，请谨慎")
        
        if 'DELETE' in sql_upper and 'WHERE' not in sql_upper:
            warnings.append("DELETE语句缺少WHERE子句，将删除所有数据")
        
        if 'UPDATE' in sql_upper and 'WHERE' not in sql_upper:
            warnings.append("UPDATE语句缺少WHERE子句，将更新所有数据")
        
        # 检查是否有SELECT *
        if re.search(r'SELECT\s+\*', sql_upper):
            warnings.append("使用SELECT * 可能影响性能，建议指定具体字段")
        
        return {
            "warnings": warnings
        }
    
    def _check_mysql_specific(self, sql: str) -> dict:
        """
        MySQL特定检查
        
        Args:
            sql: SQL语句
            
        Returns:
            检查结果
        """
        warnings = []
        sql_upper = sql.upper()
        
        # 检查LIMIT语法
        if 'LIMIT' in sql_upper:
            # MySQL LIMIT应该放在最后
            limit_pos = sql_upper.rfind('LIMIT')
            order_pos = sql_upper.rfind('ORDER')
            
            if order_pos > limit_pos:
                warnings.append("LIMIT子句应该在ORDER BY之后")
        
        return {
            "warnings": warnings
        }


# 全局实例
_checker: Optional[SyntaxChecker] = None


def get_checker() -> SyntaxChecker:
    """获取全局语法检查器实例"""
    global _checker
    if _checker is None:
        _checker = SyntaxChecker()
    return _checker


def check_syntax(sql: str, db_type: str = "mysql") -> dict:
    """
    便捷函数：检查SQL语法
    
    Args:
        sql: SQL语句
        db_type: 数据库类型
        
    Returns:
        检查结果
    """
    checker = get_checker()
    return checker.check(sql, db_type)


# 测试
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    test_cases = [
        "SELECT * FROM users WHERE id = 1",
        "SELECT * FROM users",  # 警告：SELECT *
        "DELETE FROM users",    # 警告：缺少WHERE
        "SELECT * FROM (SELECT id FROM users",  # 错误：括号不匹配
        "SELECT * FROM users WHERE name = 'test",  # 错误：引号不匹配
        "INVALID SQL",  # 错误：无效开头
    ]
    
    checker = SyntaxChecker()
    for sql in test_cases:
        result = checker.check(sql)
        print(f"SQL: {sql}")
        print(f"  Valid: {result['valid']}")
        if result['error']:
            print(f"  Error: {result['error']}")
        if result['warnings']:
            print(f"  Warnings: {result['warnings']}")
        print()
