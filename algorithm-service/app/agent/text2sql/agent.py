"""
Text2SQL Agent 核心实现
基于LangGraph的工作流编排
"""

import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.agent.text2sql.state.agent_state import AgentState, ExecutionResult
from app.agent.text2sql.template.prompt_builder import PromptBuilder
from app.agent.text2sql.template.schema_formatter import format_schema_to_m_schema, get_database_engine_info
from app.core.database import DatabaseExecutorFactory
from app.core.llm_service import get_llm_service

logger = logging.getLogger(__name__)


class Text2SqlAgent:
    """
    Text2SQL Agent
    实现完整的Text2SQL流程：Schema理解 -> SQL生成 -> 执行 -> 总结
    """
    
    def __init__(self):
        self.prompt_builder = PromptBuilder()
    
    async def analyze(
        self,
        query: str,
        datasource_config: Dict[str, Any],
        schema_info: Dict[str, Any],
        terminologies: Optional[List[Dict]] = None,
        training_examples: Optional[List[Dict]] = None,
        permission_rules: Optional[Dict] = None,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        执行完整的Text2SQL分析流程
        
        Args:
            query: 用户问题
            datasource_config: 数据源配置
            schema_info: Schema信息
            terminologies: 术语列表
            training_examples: 训练示例
            permission_rules: 权限规则
            user_id: 用户ID
            
        Returns:
            包含SQL、执行结果、总结等的字典
        """
        # 初始化状态
        state: AgentState = {
            "user_query": query,
            "db_info": schema_info,
            "table_relationship": None,
            "generated_sql": None,
            "execution_result": None,
            "report_summary": None,
            "attempts": 0,
            "correct_attempts": 0,
            "chart_type": None,
            "chart_config": None,
            "render_data": None,
            "datasource_id": None,
            "user_id": user_id,
            "filtered_sql": None,
            "recommended_questions": None,
            "used_tables": None,
            "bm25_tokens": None,
            "error_message": None,
        }
        
        try:
            # 步骤1: SQL生成
            logger.info("开始SQL生成...")
            sql = self._generate_sql(
                query=query,
                schema_info=schema_info,
                db_type=datasource_config.get("db_type", "sqlite"),
                terminologies=terminologies,
                training_examples=training_examples,
            )
            state["generated_sql"] = sql
            logger.info(f"SQL生成完成: {sql}")
            
            # 步骤2: 权限过滤
            if permission_rules:
                logger.info("开始权限过滤...")
                filtered_sql = self._apply_permissions(sql, permission_rules)
                state["filtered_sql"] = filtered_sql
                logger.info(f"权限过滤完成: {filtered_sql}")
            else:
                state["filtered_sql"] = sql
            
            # 步骤3: SQL执行
            logger.info("开始SQL执行...")
            executor = DatabaseExecutorFactory.create_executor(
                datasource_config.get("db_type", "sqlite"),
                datasource_config
            )
            execution_result = executor.execute(state["filtered_sql"])
            
            state["execution_result"] = ExecutionResult(
                success=execution_result.success,
                data=execution_result.rows if execution_result.success else None,
                error=execution_result.error if not execution_result.success else None,
            )
            logger.info(f"SQL执行完成: success={execution_result.success}")
            
            # 步骤4: 图表配置生成
            logger.info("开始图表配置生成...")
            chart_config = self._generate_chart_config(
                execution_result=execution_result.to_dict(),
                query=query,
            )
            state["chart_config"] = chart_config.get("config")
            state["render_data"] = chart_config.get("render_data")
            state["chart_type"] = chart_config.get("chart_type")
            logger.info(f"图表配置生成完成: type={chart_config.get('chart_type')}")
            
            # 步骤5: 结果总结
            logger.info("开始结果总结...")
            summary = self._generate_summary(
                query=query,
                execution_result=execution_result.to_dict(),
            )
            state["report_summary"] = summary
            logger.info(f"结果总结完成: {summary}")
            
            # 步骤6: 推荐问题
            logger.info("开始推荐问题生成...")
            recommendations = self._generate_recommendations(
                query=query,
                schema_info=schema_info,
            )
            state["recommended_questions"] = recommendations
            logger.info(f"推荐问题生成完成: {len(recommendations)}个")
            
            return {
                "success": True,
                "sql": state["generated_sql"],
                "filtered_sql": state["filtered_sql"],
                "execution_result": execution_result.to_dict(),
                "chart_config": state["chart_config"],
                "render_data": state["render_data"],
                "summary": state["report_summary"],
                "recommendations": state["recommended_questions"],
            }
            
        except Exception as e:
            logger.error(f"分析过程出错: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "sql": state.get("generated_sql"),
            }
    
    def _generate_sql(
        self,
        query: str,
        schema_info: Dict[str, Any],
        db_type: str,
        terminologies: Optional[List[Dict]] = None,
        training_examples: Optional[List[Dict]] = None,
    ) -> str:
        """
        生成SQL语句
        使用LLM生成SQL
        """
        # 格式化Schema为M-Schema格式
        db_info = {}
        for table in schema_info.get("tables", []):
            table_name = table["name"]
            fields = {}
            for field in table.get("fields", []):
                fields[field["name"]] = {
                    "type": field.get("type", "TEXT"),
                    "comment": field.get("comment", ""),
                }
            db_info[table_name] = {
                "columns": fields,
                "table_comment": table.get("comment", ""),
            }
        
        schema_str = format_schema_to_m_schema(db_info, "database", db_type)
        
        # 格式化术语
        terminologies_str = ""
        if terminologies:
            terminologies_str = "\n".join([
                f"- {t['word']}: {t['description']}"
                for t in terminologies
            ])
        
        # 格式化训练示例
        training_str = ""
        if training_examples:
            training_str = "\n\n".join([
                f"Q: {ex['question']}\nSQL: {ex['sql']}"
                for ex in training_examples[:3]  # 最多3个示例
            ])
        
        # 获取数据库引擎信息
        engine = get_database_engine_info(db_type)
        
        # 使用PromptBuilder构建提示词
        try:
            system_prompt, user_prompt = self.prompt_builder.build_sql_prompt(
                db_type=db_type,
                schema=schema_str,
                question=query,
                engine=engine,
                terminologies=terminologies_str,
                data_training=training_str,
            )
            
            # 调用LLM生成SQL
            llm_service = get_llm_service()
            result = llm_service.generate_sql(system_prompt, user_prompt)
            
            if result.get("success"):
                sql = result.get("sql", "")
                logger.info(f"LLM生成SQL成功: {sql}")
                return sql
            else:
                logger.error(f"LLM生成SQL失败: {result.get('message', '未知错误')}")
                # 降级到规则生成
                return self._generate_sql_rule_based(query, schema_info, db_type)
                
        except Exception as e:
            logger.error(f"LLM调用失败，使用规则生成: {e}")
            # 降级到规则生成
            return self._generate_sql_rule_based(query, schema_info, db_type)
    
    def _generate_sql_rule_based(
        self,
        query: str,
        schema_info: Dict[str, Any],
        db_type: str,
    ) -> str:
        """
        基于规则的SQL生成（降级方案）
        """
        query_lower = query.lower()
        
        # 查找相关表
        relevant_table = None
        for table in schema_info.get("tables", []):
            table_name_lower = table["name"].lower()
            
            if any(keyword in query_lower for keyword in ["工单", "订单", "item", "order"]):
                if "item" in table_name_lower or "order" in table_name_lower:
                    relevant_table = table
                    break
            elif any(keyword in query_lower for keyword in ["呼叫", "电话", "call"]):
                if "call" in table_name_lower:
                    relevant_table = table
                    break
            elif any(keyword in query_lower for keyword in ["地区", "区域", "area"]):
                if "area" in table_name_lower:
                    relevant_table = table
                    break
            elif any(keyword in query_lower for keyword in ["专题", "sub"]):
                if "sub" in table_name_lower:
                    relevant_table = table
                    break
        
        if not relevant_table and schema_info.get("tables"):
            relevant_table = schema_info["tables"][0]
        
        if not relevant_table:
            return "SELECT 1"
        
        table_name = relevant_table["name"]
        
        # 分析查询意图生成SQL
        if any(keyword in query_lower for keyword in ["count", "数量", "多少", "总量", "总数"]):
            count_field = None
            for field in relevant_table.get("fields", []):
                if field["name"] in ["order_cnt", "item_num", "total_num", "total_cnt", "total"]:
                    count_field = field["name"]
                    break
            
            if count_field:
                return f"SELECT SUM({count_field}) as total FROM {table_name}"
            else:
                return f"SELECT COUNT(*) as total FROM {table_name}"
        
        elif any(keyword in query_lower for keyword in ["最近", "latest", "recent", "7天", "30天"]):
            if any(f["name"] == "busi_time" for f in relevant_table.get("fields", [])):
                return f"SELECT * FROM {table_name} WHERE busi_time >= DATE('now', '-7 days') ORDER BY busi_time DESC LIMIT 100"
        
        # 默认查询
        return f"SELECT * FROM {table_name} LIMIT 100"
    
    def _apply_permissions(
        self,
        sql: str,
        permission_rules: Dict[str, Any],
    ) -> str:
        """应用权限规则"""
        filtered_sql = sql
        
        row_filters = permission_rules.get("row_filters", [])
        if row_filters:
            for filter_rule in row_filters:
                table = filter_rule.get("table", "")
                filter_str = filter_rule.get("filter", "")
                if table.lower() in sql.lower():
                    if "WHERE" in filtered_sql.upper():
                        filtered_sql = filtered_sql.replace("WHERE", f"WHERE ({filter_str}) AND ", 1)
                    else:
                        # 找到表名后的位置添加WHERE
                        table_pos = filtered_sql.upper().find(f"FROM {table.upper()}")
                        if table_pos > 0:
                            insert_pos = table_pos + len(f"FROM {table}")
                            filtered_sql = filtered_sql[:insert_pos] + f" WHERE {filter_str}" + filtered_sql[insert_pos:]
        
        return filtered_sql
    
    def _generate_chart_config(
        self,
        execution_result: Dict[str, Any],
        query: str,
    ) -> Dict[str, Any]:
        """生成图表配置"""
        if not execution_result.get("success"):
            return {
                "chart_type": "table",
                "config": {},
                "render_data": {"columns": [], "data": []},
            }
        
        columns = execution_result.get("columns", [])
        rows = execution_result.get("rows", [])
        
        # 判断图表类型
        chart_type = "table"
        if len(columns) >= 2 and len(rows) > 1:
            if any("time" in col.lower() or "date" in col.lower() for col in columns):
                chart_type = "line"
            elif len(rows) <= 10:
                chart_type = "bar"
        
        # 构建渲染数据
        render_data = {
            "columns": [{"title": col, "dataIndex": col} for col in columns],
            "data": [],
        }
        
        for row in rows:
            row_dict = {}
            for i, col in enumerate(columns):
                row_dict[col] = row[i] if i < len(row) else None
            render_data["data"].append(row_dict)
        
        return {
            "chart_type": chart_type,
            "config": {
                "type": chart_type,
                "title": "查询结果",
            },
            "render_data": render_data,
        }
    
    def _generate_summary(
        self,
        query: str,
        execution_result: Dict[str, Any],
    ) -> str:
        """生成结果总结"""
        if not execution_result.get("success"):
            return f"查询执行失败: {execution_result.get('error', '未知错误')}"
        
        try:
            # 使用LLM生成总结
            llm_service = get_llm_service()
            data_result = json.dumps(execution_result, ensure_ascii=False)
            summary = llm_service.generate_summary(data_result, query)
            return summary
        except Exception as e:
            logger.error(f"LLM总结生成失败，使用默认总结: {e}")
            # 降级到默认总结
            rows = execution_result.get("rows", [])
            row_count = execution_result.get("row_count", 0)
            
            if rows and len(rows) > 0:
                first_row = rows[0]
                if len(first_row) > 0:
                    if len(rows) == 1 and len(first_row) == 1:
                        return f"根据查询结果，{query}的答案是 {first_row[0]}"
                    else:
                        return f"查询成功，共返回 {row_count} 条数据"
            
            return f"查询执行成功，返回 {row_count} 行数据"
    
    def _generate_recommendations(
        self,
        query: str,
        schema_info: Dict[str, Any],
    ) -> List[str]:
        """生成推荐问题"""
        try:
            # 使用LLM生成推荐问题
            llm_service = get_llm_service()
            
            # 格式化Schema
            db_info = {}
            for table in schema_info.get("tables", [])[:5]:  # 最多取5张表
                table_name = table["name"]
                fields = {}
                for field in table.get("fields", []):
                    fields[field["name"]] = {
                        "type": field.get("type", "TEXT"),
                        "comment": field.get("comment", ""),
                    }
                db_info[table_name] = {
                    "columns": fields,
                    "table_comment": table.get("comment", ""),
                }
            
            schema_str = format_schema_to_m_schema(db_info, "database", "sqlite")
            
            recommendations = llm_service.generate_recommendations(
                schema=schema_str,
                current_question=query,
                num_recommendations=3,
            )
            
            if recommendations:
                return recommendations
            
            # 如果LLM返回空，使用默认推荐
            raise ValueError("LLM返回空推荐")
            
        except Exception as e:
            logger.error(f"LLM推荐问题生成失败，使用默认推荐: {e}")
            # 降级到默认推荐
            recommendations = []
            query_lower = query.lower()
            
            if any(keyword in query_lower for keyword in ["工单", "订单", "item", "order"]):
                recommendations.extend([
                    "最近30天的工单趋势如何？",
                    "哪个地区的工单量最多？",
                    "各类工单的占比情况？",
                ])
            
            if any(keyword in query_lower for keyword in ["呼叫", "电话", "call"]):
                recommendations.extend([
                    "呼叫接通率是多少？",
                    "最近7天的呼叫总量？",
                    "呼叫满意度如何？",
                ])
            
            if any(keyword in query_lower for keyword in ["地区", "区域", "area"]):
                recommendations.extend([
                    "各地区工单量排名？",
                    "哪个地区满意度最高？",
                    "地区工单处理时长对比？",
                ])
            
            if len(recommendations) < 3:
                recommendations.extend([
                    f"{query}的详细明细？",
                    f"{query}的趋势变化？",
                    "相关数据统计？",
                ])
            
            return recommendations[:5]
