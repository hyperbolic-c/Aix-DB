"""
算法服务HTTP路由
提供Text2SQL分析的流式SSE接口
"""

import json
import logging
import asyncio
from datetime import datetime
from typing import AsyncGenerator, Dict, Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.schemas.requests import (
    Text2SqlRequest,
    AlgorithmEvent,
    EventType
)
from app.agent.text2sql.agent import Text2SqlAgent

logger = logging.getLogger(__name__)
router = APIRouter()

# 创建Agent实例
text2sql_agent = Text2SqlAgent()


class Text2SqlService:
    """
    Text2SQL服务
    使用Text2SqlAgent实现工作流并流式返回事件
    """

    def __init__(self):
        self.step_name_map = {
            "schema_inspector": "表结构检索",
            "sql_generator": "SQL生成",
            "permission_filter": "权限过滤",
            "sql_executor": "SQL执行",
            "chart_generator": "图表配置生成",
            "summarizer": "结果总结",
            "recommender": "推荐问题生成",
        }

    async def analyze(
        self,
        request: Text2SqlRequest
    ) -> AsyncGenerator[AlgorithmEvent, None]:
        """
        执行Text2SQL分析
        使用Agent实现，流式返回各步骤结果
        """
        try:
            # 步骤1: Schema检索
            yield self._create_step_start("schema_inspector")
            await asyncio.sleep(0.2)
            yield self._create_step_complete(
                "schema_inspector",
                {"tables_found": len(request.schema_info.tables)}
            )

            # 步骤2: SQL生成
            yield self._create_step_start("sql_generator")
            await asyncio.sleep(0.2)
            
            # 调用Agent生成SQL
            sql = text2sql_agent._generate_sql(
                query=request.query,
                schema_info=request.schema_info.dict(),
                db_type=request.datasource_config.db_type,
                terminologies=[t.dict() for t in request.terminologies] if request.terminologies else None,
                training_examples=[t.dict() for t in request.training_examples] if request.training_examples else None,
            )
            
            yield AlgorithmEvent(
                event_type=EventType.SQL_GENERATED,
                data={"sql": sql, "chart_type": "table"},
                message="SQL生成完成"
            )
            yield self._create_step_complete("sql_generator")

            # 步骤3: 权限过滤
            filtered_sql = sql
            if request.permission_rules and (
                request.permission_rules.row_filters or
                request.permission_rules.column_permissions
            ):
                yield self._create_step_start("permission_filter")
                await asyncio.sleep(0.2)
                
                filtered_sql = text2sql_agent._apply_permissions(
                    sql,
                    request.permission_rules.dict()
                )
                
                yield AlgorithmEvent(
                    event_type=EventType.SQL_FILTERED,
                    data={"sql": filtered_sql},
                    message="权限过滤完成"
                )
                yield self._create_step_complete("permission_filter")

            # 步骤4: SQL执行
            yield self._create_step_start("sql_executor")
            
            # 调用Agent执行完整分析
            result = await text2sql_agent.analyze(
                query=request.query,
                datasource_config=request.datasource_config.dict(),
                schema_info=request.schema_info.dict(),
                terminologies=[t.dict() for t in request.terminologies] if request.terminologies else None,
                training_examples=[t.dict() for t in request.training_examples] if request.training_examples else None,
                permission_rules=request.permission_rules.dict() if request.permission_rules else None,
                user_id=request.user_id,
            )
            
            if result["success"]:
                execution_result = result["execution_result"]
                yield AlgorithmEvent(
                    event_type=EventType.SQL_EXECUTED,
                    data=execution_result,
                    message="SQL执行完成"
                )
                yield self._create_step_complete("sql_executor")

                # 步骤5: 图表配置生成
                yield self._create_step_start("chart_generator")
                await asyncio.sleep(0.2)
                
                yield AlgorithmEvent(
                    event_type=EventType.CHART_GENERATED,
                    data={
                        "chart_type": result.get("chart_type", "table"),
                        "config": result.get("chart_config", {}),
                        "render_data": result.get("render_data", {}),
                    },
                    message="图表配置生成完成"
                )
                yield self._create_step_complete("chart_generator")

                # 步骤6: 结果总结
                yield self._create_step_start("summarizer")
                await asyncio.sleep(0.2)
                
                yield AlgorithmEvent(
                    event_type=EventType.SUMMARY,
                    data={"text": result.get("summary", "")},
                    message="结果总结完成"
                )
                yield self._create_step_complete("summarizer")

                # 步骤7: 推荐问题
                yield self._create_step_start("recommender")
                await asyncio.sleep(0.2)
                
                yield AlgorithmEvent(
                    event_type=EventType.RECOMMENDATIONS,
                    data={"questions": result.get("recommendations", [])},
                    message="推荐问题生成完成"
                )
                yield self._create_step_complete("recommender")

                # 完成
                yield AlgorithmEvent(
                    event_type=EventType.COMPLETE,
                    message="全部处理完成"
                )
            else:
                # 执行失败
                yield AlgorithmEvent(
                    event_type=EventType.ERROR,
                    data={"error_type": "execution_error", "message": result.get("error", "未知错误")},
                    message=f"执行错误: {result.get('error', '未知错误')}"
                )

        except Exception as e:
            logger.error(f"分析过程出错: {e}", exc_info=True)
            yield AlgorithmEvent(
                event_type=EventType.ERROR,
                data={"error_type": "processing_error", "message": str(e)},
                message=f"处理错误: {str(e)}"
            )

    def _create_step_start(self, step_name: str) -> AlgorithmEvent:
        """创建步骤开始事件"""
        cn_name = self.step_name_map.get(step_name, step_name)
        return AlgorithmEvent(
            event_type=EventType.STEP_START,
            step_name=step_name,
            message=f"开始{cn_name}..."
        )

    def _create_step_complete(
        self,
        step_name: str,
        data: dict = None
    ) -> AlgorithmEvent:
        """创建步骤完成事件"""
        cn_name = self.step_name_map.get(step_name, step_name)
        return AlgorithmEvent(
            event_type=EventType.STEP_COMPLETE,
            step_name=step_name,
            data=data or {},
            message=f"{cn_name}完成"
        )


# 创建服务实例
text2sql_service = Text2SqlService()


@router.post("/analyze")
async def analyze(request: Text2SqlRequest):
    """
    Text2SQL分析接口

    流式返回处理过程和结果
    """
    async def event_generator():
        async for event in text2sql_service.analyze(request):
            # SSE格式: data: {json}\n\n
            yield f"data: {event.json()}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.get("/health")
async def health_check():
    """健康检查接口"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
