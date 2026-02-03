"""
结果验证器

提供SQL语法检查、执行验证等功能
不依赖算法内部实现
"""

import re
import sqlite3
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """验证结果"""
    valid: bool
    errors: List[str]
    warnings: List[str]
    details: Dict[str, Any]


class SQLSyntaxChecker:
    """
    SQL语法检查器
    
    基础的SQL语法检查，不依赖具体数据库
    """
    
    # 危险操作关键字
    DANGEROUS_KEYWORDS = [
        'DROP', 'DELETE', 'TRUNCATE', 'ALTER', 'CREATE',
        'INSERT', 'UPDATE', 'GRANT', 'REVOKE'
    ]
    
    # 必需的关键字（对于SELECT语句）
    REQUIRED_KEYWORDS = ['SELECT', 'FROM']
    
    def check(self, sql: str) -> ValidationResult:
        """
        检查SQL语法
        
        Args:
            sql: SQL语句
            
        Returns:
            验证结果
        """
        errors = []
        warnings = []
        details = {}
        
        if not sql or not sql.strip():
            errors.append("SQL语句为空")
            return ValidationResult(False, errors, warnings, details)
        
        sql_upper = sql.upper().strip()
        
        # 1. 检查危险操作
        dangerous_found = []
        for keyword in self.DANGEROUS_KEYWORDS:
            if re.search(rf'\b{keyword}\b', sql_upper):
                dangerous_found.append(keyword)
        
        if dangerous_found:
            errors.append(f"发现危险操作关键字: {', '.join(dangerous_found)}")
            details["dangerous_keywords"] = dangerous_found
        
        # 2. 检查基本结构（如果是SELECT语句）
        if sql_upper.startswith('SELECT'):
            missing = []
            for keyword in self.REQUIRED_KEYWORDS:
                if keyword not in sql_upper:
                    missing.append(keyword)
            
            if missing:
                errors.append(f"缺少必需关键字: {', '.join(missing)}")
            
            # 检查括号匹配
            open_parens = sql.count('(')
            close_parens = sql.count(')')
            if open_parens != close_parens:
                errors.append(f"括号不匹配: 左括号{open_parens}个, 右括号{close_parens}个")
            
            # 检查引号匹配
            single_quotes = sql.count("'") - sql.count("\\'")
            if single_quotes % 2 != 0:
                warnings.append("单引号数量为奇数，可能存在未闭合的字符串")
        
        # 3. 检查SQL长度
        if len(sql) > 10000:
            warnings.append(f"SQL语句过长 ({len(sql)} 字符)")
        
        details["sql_length"] = len(sql)
        details["has_dangerous"] = len(dangerous_found) > 0
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )


class ExecutionValidator:
    """
    SQL执行验证器
    
    执行SQL并验证结果
    """
    
    def __init__(self, db_path: str):
        """
        初始化
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
    
    def validate(
        self,
        sql: str,
        timeout: int = 10,
        check_has_data: bool = True
    ) -> ValidationResult:
        """
        验证SQL执行
        
        Args:
            sql: SQL语句
            timeout: 超时时间（秒）
            check_has_data: 是否检查有返回数据
            
        Returns:
            验证结果
        """
        errors = []
        warnings = []
        details = {
            "execution_time_ms": 0,
            "row_count": 0,
            "column_count": 0,
            "columns": []
        }
        
        try:
            # 连接数据库
            conn = sqlite3.connect(self.db_path, timeout=timeout)
            cursor = conn.cursor()
            
            # 设置超时
            conn.execute(f"PRAGMA busy_timeout = {timeout * 1000}")
            
            # 执行SQL
            import time
            start_time = time.time()
            cursor.execute(sql)
            execution_time = (time.time() - start_time) * 1000
            
            # 获取结果
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            
            # 填充详情
            details["execution_time_ms"] = round(execution_time, 2)
            details["row_count"] = len(rows)
            details["column_count"] = len(columns)
            details["columns"] = columns
            details["sample_rows"] = rows[:3]  # 前3行作为样本
            
            # 检查是否有数据
            if check_has_data and len(rows) == 0:
                warnings.append("SQL执行成功，但返回0行数据")
            
            conn.close()
            
        except sqlite3.Error as e:
            errors.append(f"SQL执行错误: {str(e)}")
        except Exception as e:
            errors.append(f"执行异常: {str(e)}")
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )


class ResultValidator:
    """
    结果验证器
    
    验证执行结果是否符合预期
    """
    
    def validate_structure(
        self,
        result: Dict[str, Any],
        expected_columns: Optional[List[str]] = None,
        min_rows: Optional[int] = None,
        max_rows: Optional[int] = None
    ) -> ValidationResult:
        """
        验证结果结构
        
        Args:
            result: 执行结果
            expected_columns: 期望的列名列表
            min_rows: 最小行数
            max_rows: 最大行数
            
        Returns:
            验证结果
        """
        errors = []
        warnings = []
        details = {}
        
        # 检查基本结构
        if not result.get("success"):
            errors.append("执行未成功")
            return ValidationResult(False, errors, warnings, details)
        
        rows = result.get("rows", [])
        columns = result.get("columns", [])
        
        # 检查列
        if expected_columns:
            missing = set(expected_columns) - set(columns)
            if missing:
                errors.append(f"缺少期望的列: {', '.join(missing)}")
            details["expected_columns"] = expected_columns
            details["actual_columns"] = columns
        
        # 检查行数
        row_count = len(rows)
        details["row_count"] = row_count
        
        if min_rows is not None and row_count < min_rows:
            errors.append(f"行数不足: 期望至少{min_rows}行，实际{row_count}行")
        
        if max_rows is not None and row_count > max_rows:
            warnings.append(f"行数过多: 期望最多{max_rows}行，实际{row_count}行")
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )
