"""
API 路由
Text2SQL Service 的 HTTP API 接口
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any

from ..schemas.requests import (
    SQLGenerateRequest,
    SQLGenerateResponse,
    HealthResponse
)
from ..generator.sql_generator import SQLGenerator

router = APIRouter()
sql_generator = SQLGenerator()


@router.post("/sql/generate", response_model=SQLGenerateResponse)
async def generate_sql(request: SQLGenerateRequest) -> SQLGenerateResponse:
    """生成 SQL
    
    接收完整的上下文信息，包括：
    - Schema 信息（全量表结构）
    - 数据库类型和名称
    - 表关系
    - LLM 配置
    - 多轮对话历史
    - 术语和训练示例
    - 错误信息（用于纠错）
    
    服务不连接数据库，所有信息通过请求传入。
    """
    try:
        result = await sql_generator.generate(request)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """健康检查"""
    return HealthResponse(
        status="healthy",
        version="1.0.0"
    )
