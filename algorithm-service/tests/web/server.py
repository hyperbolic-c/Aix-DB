"""
测试框架 Web 服务
为前端提供 API 支持
"""

import sys
import json
import asyncio
from pathlib import Path
from typing import Dict, Any, List
from dataclasses import dataclass

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from framework.request_builder import CompetitionRequestBuilder, ExcelSchemaLoader
from framework.validators import SQLSyntaxChecker, ExecutionValidator

app = FastAPI(title="测试框架 API", version="1.0.0")

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局实例
builder = CompetitionRequestBuilder("target_db/competition")
schema_loader = ExcelSchemaLoader("target_db/competition/finalTableSchema.xlsx")
syntax_checker = SQLSyntaxChecker()


class TestRequest(BaseModel):
    """测试请求"""
    query: str
    datasource_config: Dict[str, Any]
    schema_info: Dict[str, Any]
    schema_mode: str = "related"  # primary, related, all
    case_id: int = None


@app.get("/api/test-framework/gold-cases")
async def get_gold_cases(
    limit: int = 10,
    offset: int = 0,
    search: str = None
) -> Dict[str, Any]:
    """获取 Gold 用例列表（支持分页和搜索）
    
    Args:
        limit: 返回数量限制，默认10
        offset: 偏移量，默认0
        search: 搜索关键词（匹配问题内容）
    """
    try:
        # 加载所有用例
        all_cases = builder.load_all_gold_cases()
        
        # 搜索过滤
        if search:
            search_lower = search.lower()
            filtered_cases = [
                c for c in all_cases 
                if search_lower in c["question"].lower() or 
                   search_lower in str(c.get("table", "")).lower() or
                   search_lower in str(c["id"])
            ]
        else:
            filtered_cases = all_cases
        
        # 分页
        total = len(filtered_cases)
        paginated_cases = filtered_cases[offset:offset + limit]
        
        return {
            "cases": [
                {
                    "id": c["id"],
                    "question": c["question"],
                    "sql": c["sql"],
                    "table": c.get("table", ""),
                    "level": c.get("level", 1)
                }
                for c in paginated_cases
            ],
            "total": total,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/test-framework/gold-cases/{case_id}")
async def get_gold_case(case_id: int) -> Dict[str, Any]:
    """获取单个 Gold 用例"""
    try:
        case = builder._load_gold_case(case_id)
        if not case:
            raise HTTPException(status_code=404, detail=f"用例 #{case_id} 不存在")
        return {
            "id": case["id"],
            "question": case["question"],
            "sql": case["sql"],
            "table": case.get("table", ""),
            "level": case.get("level", 1)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/test-framework/schema-stats")
async def get_schema_stats() -> Dict[str, Any]:
    """获取 Schema 统计信息"""
    try:
        stats = builder.get_statistics()
        return {
            "total_tables": stats["schema_tables"],
            "tables": schema_loader.list_all_tables()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/test-framework/run")
async def run_test(request: TestRequest) -> Dict[str, Any]:
    """运行测试"""
    try:
        # 根据 schema_mode 构建请求
        include_all = request.schema_mode == "all"
        include_related = request.schema_mode == "related"
        
        if request.case_id:
            # 使用 Gold 用例
            case = builder._load_gold_case(request.case_id)
            if not case:
                raise HTTPException(status_code=404, detail=f"用例 #{request.case_id} 不存在")
            
            # 构建请求
            test_request = builder.build_request(
                case_id=request.case_id,
                include_related_tables=include_related,
                include_all_tables=include_all
            )
        else:
            # 使用自定义问题
            # 简化处理：使用默认表
            test_request = {
                "query": request.query,
                "datasource_config": request.datasource_config,
                "schema_info": {"tables": []},
                "terminologies": [],
                "training_examples": [],
                "permission_rules": {},
                "user_id": 1
            }
        
        # 返回简化结果（实际应该调用算法服务）
        # 这里先返回模拟数据
        return {
            "sql": f"-- 模拟生成的 SQL\nSELECT * FROM example WHERE question = '{request.query[:20]}...'",
            "execution_result": {
                "data": [
                    {"id": 1, "name": "示例数据1", "value": 100},
                    {"id": 2, "name": "示例数据2", "value": 200},
                    {"id": 3, "name": "示例数据3", "value": 300}
                ],
                "row_count": 3,
                "execution_time_ms": 15
            },
            "chart_config": {
                "type": "bar",
                "x_field": "name",
                "y_field": "value"
            },
            "summary": f"根据问题 \"{request.query[:30]}...\" 查询到 3 条数据",
            "success": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "service": "test-framework-api"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
