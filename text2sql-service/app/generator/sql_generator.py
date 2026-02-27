"""
SQL 生成器
从原实现 agent/text2sql/sql/generator.py 迁移
处理完整上下文，无数据库连接
"""

import json
import re
from typing import List, Dict, Optional, Any
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from .retriever import SchemaRetriever, SimpleSchemaRetriever
from .prompt_builder import PromptBuilder
from ..template.schema_formatter import format_schema_to_m_schema, get_database_engine_info
from ..schemas.requests import SQLGenerateRequest, SQLGenerateResponse


class SQLGenerator:
    """SQL 生成器 - 完整信息处理，无数据库连接"""
    
    async def generate(self, request: SQLGenerateRequest) -> SQLGenerateResponse:
        """生成 SQL - 处理完整上下文
        
        Args:
            request: SQL 生成请求，包含所有必要信息
            
        Returns:
            SQL 生成响应
        """
        try:
            # 1. Schema 检索（BM25）
            tables_data = [t.model_dump() for t in request.tables]
            
            # 尝试使用 BM25，如果失败则使用简单匹配
            try:
                retriever = SchemaRetriever(tables_data)
            except Exception:
                retriever = SimpleSchemaRetriever(tables_data)
            
            retrieved_tables, tokens = retriever.retrieve(request.query, request.top_k)
            
            # 2. 获取表结构（包含表关系补充）
            table_info = retriever.get_table_info(retrieved_tables)
            
            # 如果有表关系，补充关联表
            if request.table_relations:
                table_info = self._supplement_related_tables(
                    table_info, 
                    request.table_relations,
                    retriever.tables
                )
            
            # 3. 格式化 Schema 为 M-Schema
            schema_str = format_schema_to_m_schema(
                db_info={t["name"]: t for t in table_info},
                db_name=request.db_name or "database",
                db_type=request.db_type
            )
            
            # 4. 构建提示词（传入完整上下文）
            builder = PromptBuilder()
            chat_history = [m.model_dump() for m in request.chat_history] if request.chat_history else None
            
            system_prompt, user_prompt = builder.build_sql_prompt(
                db_type=request.db_type,
                schema=schema_str,
                question=request.query,
                engine=get_database_engine_info(request.db_type),
                chat_history=chat_history,
                terminologies=request.terminologies or "",
                training_examples=request.training_examples or "",
                error_msg=request.error_message or "",
                current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                enable_query_limit=request.enable_query_limit,
                change_title=request.change_title,
                lang=request.lang
            )
            
            # 5. 调用 LLM
            llm = self._create_llm(request.llm)
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            response = await llm.ainvoke(messages)
            
            # 6. 解析结果
            result = self._parse_response(response.content)
            
            return SQLGenerateResponse(
                success=result.get("success", True),
                sql=result.get("sql"),
                chart_type=result.get("chart_type") or result.get("chart-type", "table"),
                used_tables=result.get("tables", []),
                brief=result.get("brief"),
                retrieved_tables=retrieved_tables,
                tokens=tokens,
                message=result.get("message")
            )
            
        except Exception as e:
            return SQLGenerateResponse(
                success=False,
                message=f"生成失败: {str(e)}"
            )
    
    def _supplement_related_tables(
        self, 
        table_info: List[Dict], 
        relations: List[Any],
        all_tables: Dict
    ) -> List[Dict]:
        """根据表关系补充关联表
        
        Args:
            table_info: 当前表信息列表
            relations: 表关系列表
            all_tables: 所有表的字典
            
        Returns:
            补充后的表信息列表
        """
        current_names = {t["name"] for t in table_info}
        
        for rel in relations:
            from_table = getattr(rel, 'from_table', None) or rel.get('from_table')
            to_table = getattr(rel, 'to_table', None) or rel.get('to_table')
            
            for table_name in [from_table, to_table]:
                if table_name and table_name not in current_names and table_name in all_tables:
                    table_info.append(all_tables[table_name])
                    current_names.add(table_name)
        
        return table_info
    
    def _create_llm(self, config) -> ChatOpenAI:
        """创建 LLM 实例
        
        Args:
            config: LLM 配置
            
        Returns:
            ChatOpenAI 实例
        """
        # 处理不同 provider
        provider = config.provider.lower()
        
        if provider == "openai":
            return ChatOpenAI(
                model=config.model,
                api_key=config.api_key,
                base_url=config.base_url,
                temperature=config.temperature,
                timeout=config.timeout
            )
        elif provider in ["azure", "azure_openai"]:
            # Azure OpenAI
            return ChatOpenAI(
                model=config.model,
                api_key=config.api_key,
                base_url=config.base_url,
                temperature=config.temperature,
                timeout=config.timeout
            )
        elif provider == "ollama":
            # Ollama 本地模型
            base_url = config.base_url or "http://localhost:11434"
            return ChatOpenAI(
                model=config.model,
                api_key="ollama",  # Ollama 不需要 API key
                base_url=f"{base_url}/v1",
                temperature=config.temperature,
                timeout=config.timeout
            )
        else:
            # 默认使用 OpenAI 格式
            return ChatOpenAI(
                model=config.model,
                api_key=config.api_key,
                base_url=config.base_url,
                temperature=config.temperature,
                timeout=config.timeout
            )
    
    def _parse_response(self, content: str) -> Dict[str, Any]:
        """解析 LLM 响应
        
        Args:
            content: LLM 返回的文本内容
            
        Returns:
            解析后的字典
        """
        # 清理 markdown
        content = re.sub(r'```json\s*', '', content)
        content = re.sub(r'```\s*', '', content)
        content = content.strip()
        
        # 尝试解析 JSON
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # 尝试修复转义序列
            try:
                def fix_sql_field(match):
                    prefix = match.group(1)
                    sql_content = match.group(2)
                    suffix = match.group(3)
                    # 修复 SQL 中的转义换行
                    fixed_sql = re.sub(r'\\\s*\n\s*', ' ', sql_content)
                    return f'{prefix}{fixed_sql}{suffix}'
                
                fixed_content = re.sub(
                    r'("sql"\s*:\s*")(.*?)((?:\s*",)|(?:"\s*[,}]))',
                    fix_sql_field,
                    content,
                    flags=re.DOTALL
                )
                return json.loads(fixed_content)
            except Exception:
                # 尝试提取 SQL
                sql_match = re.search(r'["\']sql["\']\s*:\s*["\']([^"\']+)["\']', content)
                if sql_match:
                    return {
                        "success": True,
                        "sql": sql_match.group(1),
                        "chart_type": "table",
                        "tables": []
                    }
                return {
                    "success": False,
                    "message": f"无法解析响应: {content[:200]}"
                }
