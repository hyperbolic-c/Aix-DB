"""
迭代生成器
带验证的SQL生成，支持失败后重新生成
"""

import logging
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass

from agent.text2sql.validation import SQLValidator, ValidationResult
from agent.text2sql.rewrite import QuestionRewriter

logger = logging.getLogger(__name__)


@dataclass
class GenerationResult:
    """生成结果"""
    sql: str
    success: bool
    attempts: int
    final_validation: ValidationResult
    history: list


class IterativeGenerator:
    """
    迭代生成器
    生成SQL并验证，失败时根据反馈重新生成
    """
    
    def __init__(
        self,
        validator: Optional[SQLValidator] = None,
        rewriter: Optional[QuestionRewriter] = None,
        max_retries: int = 3
    ):
        """
        初始化迭代生成器
        
        Args:
            validator: SQL验证器
            rewriter: 问题改写器
            max_retries: 最大重试次数
        """
        self.validator = validator or SQLValidator()
        self.rewriter = rewriter or QuestionRewriter()
        self.max_retries = max_retries
    
    def generate(
        self,
        question: str,
        generate_func: Callable[[str], str],
        schema: Optional[Dict[str, Any]] = None,
        db_type: str = "mysql"
    ) -> GenerationResult:
        """
        生成SQL（带验证和重试）
        
        Args:
            question: 用户问题
            generate_func: SQL生成函数
            schema: Schema信息
            db_type: 数据库类型
            
        Returns:
            生成结果
        """
        history = []
        current_question = question
        best_sql = ""
        best_score = 0.0
        
        for attempt in range(1, self.max_retries + 1):
            logger.info(f"SQL生成尝试 {attempt}/{self.max_retries}")
            
            # 1. 生成SQL
            try:
                sql = generate_func(current_question)
            except Exception as e:
                logger.error(f"生成SQL失败: {e}")
                history.append({
                    "attempt": attempt,
                    "error": f"生成失败: {str(e)}"
                })
                continue
            
            # 2. 验证SQL
            validation = self.validator.validate(
                question=question,
                sql=sql,
                schema=schema,
                db_type=db_type
            )
            
            history.append({
                "attempt": attempt,
                "sql": sql,
                "validation": validation
            })
            
            # 3. 记录最佳结果
            if validation.score > best_score:
                best_score = validation.score
                best_sql = sql
            
            # 4. 检查是否通过
            if validation.valid and validation.score >= 0.7:
                logger.info(f"SQL生成成功（尝试 {attempt} 次）")
                return GenerationResult(
                    sql=sql,
                    success=True,
                    attempts=attempt,
                    final_validation=validation,
                    history=history
                )
            
            # 5. 准备下一次尝试
            if attempt < self.max_retries:
                current_question = self._prepare_retry(
                    question=question,
                    sql=sql,
                    validation=validation,
                    attempt=attempt
                )
        
        # 达到最大重试次数，返回最佳结果
        logger.warning(f"达到最大重试次数，返回最佳结果（得分: {best_score:.2f}）")
        return GenerationResult(
            sql=best_sql,
            success=best_score >= 0.5,  # 至少得分0.5才算成功
            attempts=self.max_retries,
            final_validation=history[-1]["validation"] if history else ValidationResult(valid=False),
            history=history
        )
    
    def _prepare_retry(
        self,
        question: str,
        sql: str,
        validation: ValidationResult,
        attempt: int
    ) -> str:
        """
        准备重试的问题
        
        Args:
            question: 原始问题
            sql: 生成的SQL
            validation: 验证结果
            attempt: 当前尝试次数
            
        Returns:
            优化后的问题
        """
        feedback_parts = [question]
        
        # 添加前一次的错误信息
        if validation.failed_checks:
            for failed in validation.failed_checks:
                check_type = failed.get("check", "")
                error = failed.get("error", "")
                
                if check_type == "syntax":
                    feedback_parts.append(f"注意：SQL语法有误 - {error}")
                elif check_type == "semantic":
                    feedback_parts.append(f"注意：SQL语义不匹配 - {error}")
                elif check_type == "schema":
                    feedback_parts.append(f"注意：Schema问题 - {error}")
        
        # 添加警告（如果是最后一次尝试前的警告）
        if attempt == self.max_retries - 1 and validation.warnings:
            feedback_parts.append(f"注意：{validation.warnings[0]}")
        
        # 添加改进建议
        feedback_parts.append("请修正上述问题重新生成SQL。")
        
        return "\n".join(feedback_parts)


# 全局实例
_generator: Optional[IterativeGenerator] = None


def get_generator() -> IterativeGenerator:
    """获取全局迭代生成器实例"""
    global _generator
    if _generator is None:
        _generator = IterativeGenerator()
    return _generator


def generate_with_validation(
    question: str,
    generate_func: Callable[[str], str],
    schema: Optional[Dict[str, Any]] = None,
    db_type: str = "mysql",
    max_retries: int = 3
) -> GenerationResult:
    """
    便捷函数：带验证的SQL生成
    
    Args:
        question: 用户问题
        generate_func: SQL生成函数
        schema: Schema信息
        db_type: 数据库类型
        max_retries: 最大重试次数
        
    Returns:
        生成结果
    """
    generator = IterativeGenerator(max_retries=max_retries)
    return generator.generate(question, generate_func, schema, db_type)
