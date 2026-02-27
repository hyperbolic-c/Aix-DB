"""
提示词构建器
从原实现 agent/text2sql/template/prompt_builder.py 迁移
支持完整上下文：多轮对话、术语、训练示例、错误信息等
"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime

from ..template.template_loader import get_template_loader
from ..template.schema_formatter import (
    build_terminologies_section,
    build_training_examples_section
)


class PromptBuilder:
    """支持完整上下文的提示词构建器"""
    
    def __init__(self):
        self.template_loader = get_template_loader()
        self.base_template = self.template_loader.load_base_template()
    
    def build_sql_prompt(
        self,
        db_type: str,
        schema: str,
        question: str,
        engine: str,
        chat_history: Optional[List[Dict]] = None,
        terminologies: str = "",
        training_examples: str = "",
        error_msg: str = "",
        current_time: Optional[str] = None,
        enable_query_limit: bool = True,
        change_title: bool = False,
        lang: str = "简体中文"
    ) -> Tuple[str, str]:
        """构建 SQL 生成提示词
        
        包含原实现中的所有信息：
        - 数据库引擎信息
        - Schema (M-Schema格式)
        - 术语定义
        - 训练示例
        - 多轮对话历史
        - 错误信息（纠错）
        """
        # 加载数据库特定模板
        sql_template_dict = self.template_loader.load_sql_template(db_type)
        sql_template = sql_template_dict.get('template', sql_template_dict)
        sql_base_template = self.base_template['template']['sql']
        
        # 获取 process_check
        process_check = sql_template.get('process_check') or sql_base_template['process_check']
        
        # 获取 query_limit 规则
        query_limit = sql_base_template['query_limit'] if enable_query_limit else sql_base_template['no_query_limit']
        
        # 组合基础 SQL 规则
        base_sql_rules = (
            sql_template.get('quot_rule', '') + 
            query_limit + 
            sql_template.get('limit_rule', '') + 
            sql_template.get('other_rule', '')
        )
        
        # 获取示例
        sql_examples = sql_template.get('basic_example', sql_base_template.get('basic_example', ''))
        example_engine = sql_template.get('example_engine', 'MySQL 8.0')
        example_answer_1 = sql_template.get('example_answer_1_with_limit' if enable_query_limit else 'example_answer_1', '')
        example_answer_2 = sql_template.get('example_answer_2_with_limit' if enable_query_limit else 'example_answer_2', '')
        example_answer_3 = sql_template.get('example_answer_3_with_limit' if enable_query_limit else 'example_answer_3', '')
        
        # 构建系统提示词
        system_prompt = sql_base_template['system'].format(
            engine=engine,
            schema=schema,
            question=question,
            lang=lang,
            terminologies=terminologies,
            data_training=training_examples,
            custom_prompt="",  # 原实现中为空
            process_check=process_check,
            base_sql_rules=base_sql_rules,
            basic_sql_examples=sql_examples,
            example_engine=example_engine,
            example_answer_1=example_answer_1,
            example_answer_2=example_answer_2,
            example_answer_3=example_answer_3,
        )
        
        # 构建用户提示词
        if current_time is None:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 构建多轮对话上下文
        chat_context = ""
        if chat_history:
            chat_context = "\n## 对话历史\n\n"
            for msg in chat_history:
                role = "用户" if msg.get("role") == "user" else "助手"
                chat_context += f"{role}: {msg.get('content', '')}\n"
                if msg.get("sql") and msg.get("role") == "assistant":
                    chat_context += f"生成的SQL: {msg['sql']}\n"
                chat_context += "\n"
        
        # 构建错误信息
        error_context = ""
        if error_msg:
            error_context = f"\n## 上次错误\n上次生成的SQL执行出错: {error_msg}\n请修正SQL。\n"
        
        user_prompt = sql_base_template['user'].format(
            engine=engine,
            schema=schema,
            question=question,
            rule="",
            current_time=current_time,
            error_msg=error_msg,
            change_title=change_title,
        )
        
        # 在 user_prompt 前添加对话上下文
        user_prompt = chat_context + error_context + user_prompt
        
        return system_prompt, user_prompt
