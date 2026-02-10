"""
测试框架 Web 服务
为前端提供 API 支持
"""

import sys
import json
import asyncio
import httpx
import sqlite3
import logging
from pathlib import Path
from typing import Dict, Any, List
from dataclasses import dataclass
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 配置日志输出到指定目录
LOG_DIR = Path(__file__).parent.parent / "test_logs"
LOG_DIR.mkdir(exist_ok=True)

# 创建文件处理器
log_file = LOG_DIR / f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setLevel(logging.INFO)

# 创建控制台处理器
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# 设置日志格式
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# 配置根日志记录器
logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, console_handler]
)

logger = logging.getLogger(__name__)
logger.info(f"日志输出目录: {LOG_DIR}")
logger.info(f"当前日志文件: {log_file}")

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
execution_validator = ExecutionValidator("target_db/competition/final.db")

# 算法服务配置
ALGORITHM_SERVICE_URL = "http://localhost:8002"


class TestRequest(BaseModel):
    """测试请求"""
    query: str
    datasource_config: Dict[str, Any]
    schema_info: Dict[str, Any]
    schema_mode: str = "related"  # primary, related, all
    case_id: int = None


async def call_analyze_service(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    调用算法服务的 /api/v1/analyze 接口
    
    Args:
        request_data: 符合 Text2SqlRequest 的请求数据
        
    Returns:
        解析后的完整结果
    """
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(
                f"{ALGORITHM_SERVICE_URL}/api/v1/analyze",
                json=request_data,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            
            # 解析 SSE 流式响应
            result = {
                "sql": None,
                "chart_config": None,
                "summary": None,
                "recommendations": [],
                "steps": []
            }
            
            # 读取 SSE 流
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    try:
                        event_data = json.loads(line[6:])  # 去掉 "data: " 前缀
                        event_type = event_data.get("event_type")
                        step_name = event_data.get("step_name")
                        data = event_data.get("data", {})
                        
                        # 记录步骤
                        if event_type in ["step_start", "step_complete", "step_error"]:
                            result["steps"].append({
                                "type": event_type,
                                "name": step_name,
                                "message": event_data.get("message", ""),
                                "data": data
                            })
                        
                        # 提取关键结果（从数据生成事件）
                        # 注意：字段名需要与算法服务返回的一致
                        if event_type == "sql_generated":
                            result["sql"] = data.get("sql")
                        elif event_type == "sql_filtered":
                            result["filtered_sql"] = data.get("sql")
                        elif event_type == "sql_executed":
                            # 算法服务直接返回 execution_result 对象
                            result["execution_result"] = data
                        elif event_type == "chart_generated":
                            result["chart_config"] = {
                                "type": data.get("chart_type", "table"),
                                "config": data.get("config", {}),
                                "render_data": data.get("render_data", {})
                            }
                        elif event_type == "summary":
                            # 算法服务返回 {"text": summary}
                            result["summary"] = data.get("text", "")
                        elif event_type == "recommendations":
                            # 算法服务返回 {"questions": [...]}
                            result["recommendations"] = data.get("questions", [])
                        elif event_type == "complete":
                            # 完整结果汇总
                            if data:
                                result["sql"] = data.get("sql", result["sql"])
                                result["chart_config"] = data.get("chart_config", result["chart_config"])
                                result["summary"] = data.get("summary", result["summary"])
                                result["recommendations"] = data.get("recommendations", result["recommendations"])
                        
                        # 处理错误
                        if event_type == "error":
                            raise Exception(event_data.get("message", "算法服务返回错误"))
                            
                    except json.JSONDecodeError:
                        continue
            
            return result
            
        except httpx.ConnectError:
            raise Exception(f"无法连接到算法服务 {ALGORITHM_SERVICE_URL}")
        except httpx.TimeoutException:
            raise Exception("算法服务调用超时")
        except Exception as e:
            raise Exception(f"调用算法服务失败: {str(e)}")


def execute_sql_query(sql: str, db_path: str) -> Dict[str, Any]:
    """
    执行SQL查询
    
    Args:
        sql: SQL语句
        db_path: 数据库路径
        
    Returns:
        执行结果
    """
    import time
    start_time = time.time()
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(sql)
        
        # 获取列名
        columns = [description[0] for description in cursor.description] if cursor.description else []
        
        # 获取数据
        rows = cursor.fetchall()
        data = [dict(row) for row in rows]
        
        conn.close()
        
        execution_time = int((time.time() - start_time) * 1000)
        
        return {
            "data": data,
            "row_count": len(data),
            "execution_time_ms": execution_time,
            "columns": columns
        }
        
    except sqlite3.Error as e:
        raise Exception(f"SQL执行错误: {str(e)}")
    except Exception as e:
        raise Exception(f"执行查询失败: {str(e)}")


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
    """运行测试 - 真实调用算法服务，验证完整6步骤流程"""
    start_time = datetime.now()
    test_id = f"test_{start_time.strftime('%Y%m%d_%H%M%S')}_{request.case_id or 'custom'}"
    
    # 初始化步骤验证结果
    step_validation = {
        "step1_sql_generation": {"status": "pending", "details": {}},
        "step2_permission_filter": {"status": "pending", "details": {}},
        "step3_sql_execution": {"status": "pending", "details": {}},
        "step4_chart_config": {"status": "pending", "details": {}},
        "step5_summary": {"status": "pending", "details": {}},
        "step6_recommendations": {"status": "pending", "details": {}},
    }
    
    logger.info("=" * 80)
    logger.info(f"[全流程测试开始] ID: {test_id}")
    logger.info(f"[测试参数] case_id={request.case_id}, schema_mode={request.schema_mode}")
    logger.info(f"[测试问题] {request.query}")
    logger.info("=" * 80)
    
    try:
        # ========== 阶段1: 构建测试请求 ==========
        logger.info("[阶段1] 构建测试请求...")
        
        # 根据 schema_mode 构建请求
        include_all = request.schema_mode == "all"
        include_related = request.schema_mode == "related"
        
        if request.case_id:
            logger.info(f"[阶段1.1] 加载Gold用例 #{request.case_id}")
            case = builder._load_gold_case(request.case_id)
            if not case:
                raise HTTPException(status_code=404, detail=f"用例 #{request.case_id} 不存在")
            logger.info(f"[阶段1.1] ✓ 用例加载成功: {case['question'][:50]}...")
            
            logger.info(f"[阶段1.2] 从Excel构建请求 (include_related={include_related}, include_all={include_all})")
            test_request = builder.build_request(
                case_id=request.case_id,
                include_related_tables=include_related,
                include_all_tables=include_all
            )
            logger.info(f"[阶段1.2] ✓ 请求构建完成，Schema包含 {len(test_request.get('schema_info', {}).get('tables', []))} 张表")
        else:
            logger.info("[阶段1.1] 使用自定义问题")
            if include_all:
                logger.info("[阶段1.2] 加载所有表")
                all_tables = schema_loader.load_schema()["tables"]
                table_names = [t["name"] for t in all_tables]
            elif include_related and request.datasource_config.get("primary_table"):
                primary_table = request.datasource_config.get("primary_table")
                logger.info(f"[阶段1.2] 加载与 {primary_table} 相关的表")
                related_tables = schema_loader.get_related_tables(primary_table)
                table_names = [t["name"] for t in related_tables]
            else:
                logger.info("[阶段1.2] 加载前5张表")
                table_names = schema_loader.list_all_tables()[:5]
            
            logger.info(f"[阶段1.2] ✓ 将加载 {len(table_names)} 张表: {table_names}")
            
            tables = []
            for table_name in table_names:
                table_schema = schema_loader.get_table_schema(table_name)
                if table_schema:
                    tables.append({
                        "name": table_schema["name"],
                        "comment": table_schema.get("comment", ""),
                        "fields": [
                            {
                                "name": f["name"],
                                "type": f["type"],
                                "comment": f.get("comment", "")
                            }
                            for f in table_schema["fields"]
                        ]
                    })
            
            logger.info(f"[阶段1.2] ✓ Schema构建完成，共 {len(tables)} 张表")
            
            test_request = {
                "query": request.query,
                "datasource_config": request.datasource_config,
                "schema_info": {"tables": tables},
                "terminologies": [],
                "training_examples": [],
                "chat_history": [],
                "user_id": 1,
                "datasource_id": 1
            }
        
        # 转换 datasource_config 格式
        # 使用绝对路径，确保算法服务能找到数据库文件
        db_path = str(Path("target_db/competition/final.db").resolve())
        if isinstance(test_request["datasource_config"], dict):
            if "db_path" in test_request["datasource_config"]:
                db_path = str(Path(test_request["datasource_config"]["db_path"]).resolve())
        
        test_request["datasource_config"] = {
            "db_type": "sqlite",
            "host": "localhost",
            "port": 0,
            "database": db_path,
            "username": "",
            "password": ""
        }
        
        logger.info(f"[阶段1.3] 数据库路径: {db_path}")
        
        # ========== 阶段2: 调用算法服务 ==========
        logger.info("[阶段2] 调用算法服务...")
        logger.info(f"[阶段2] 请求体摘要: {json.dumps(test_request, ensure_ascii=False, default=str)[:300]}...")
        
        algorithm_result = await call_analyze_service(test_request)
        
        logger.info("[阶段2] ✓ 算法服务调用完成")
        
        # ========== 阶段3: 验证算法6步骤 ==========
        logger.info("=" * 80)
        logger.info("[阶段3] 验证算法完整6步骤流程")
        logger.info("=" * 80)
        
        # 步骤1: SQL生成验证
        logger.info("[步骤1/6] SQL生成验证...")
        sql = algorithm_result.get("sql")
        if sql:
            step_validation["step1_sql_generation"]["status"] = "success"
            step_validation["step1_sql_generation"]["details"] = {
                "sql": sql[:200] + "..." if len(sql) > 200 else sql,
                "sql_length": len(sql)
            }
            logger.info(f"[步骤1/6] ✓ SQL生成成功: {sql[:100]}...")
        else:
            step_validation["step1_sql_generation"]["status"] = "failed"
            step_validation["step1_sql_generation"]["details"] = {"error": "未生成SQL"}
            logger.error("[步骤1/6] ✗ SQL生成失败")
            return {
                "success": False,
                "error": "算法服务未能生成SQL",
                "step_validation": step_validation,
                "steps": algorithm_result.get("steps", [])
            }
        
        # 步骤2: 权限过滤验证
        logger.info("[步骤2/6] 权限过滤验证...")
        filtered_sql = algorithm_result.get("filtered_sql")
        if filtered_sql:
            step_validation["step2_permission_filter"]["status"] = "success"
            step_validation["step2_permission_filter"]["details"] = {
                "filtered_sql": filtered_sql[:200] + "..." if len(filtered_sql) > 200 else filtered_sql,
                "has_permission_filter": filtered_sql != sql
            }
            logger.info(f"[步骤2/6] ✓ 权限过滤完成")
            if filtered_sql != sql:
                logger.info(f"[步骤2/6]   过滤后SQL: {filtered_sql[:100]}...")
        else:
            # 没有权限过滤也是正常的（如果没有配置权限规则）
            step_validation["step2_permission_filter"]["status"] = "skipped"
            step_validation["step2_permission_filter"]["details"] = {"reason": "未应用权限过滤"}
            logger.info("[步骤2/6] - 未应用权限过滤（可能无权限规则）")
        
        # 步骤3: SQL执行验证
        logger.info("[步骤3/6] SQL执行验证...")
        execution_result_from_algo = algorithm_result.get("execution_result")
        
        # 同时执行本地SQL验证
        try:
            local_execution_result = execute_sql_query(sql, db_path)
            local_success = True
        except Exception as e:
            local_execution_result = {"error": str(e), "row_count": 0, "data": []}
            local_success = False
            logger.error(f"[步骤3/6] 本地SQL执行失败: {e}")
        
        if execution_result_from_algo and execution_result_from_algo.get("success"):
            step_validation["step3_sql_execution"]["status"] = "success"
            step_validation["step3_sql_execution"]["details"] = {
                "algorithm_row_count": execution_result_from_algo.get("row_count", 0),
                "local_row_count": local_execution_result.get("row_count", 0),
                "local_success": local_success,
                "columns": execution_result_from_algo.get("columns", [])
            }
            logger.info(f"[步骤3/6] ✓ SQL执行成功")
            logger.info(f"[步骤3/6]   算法返回行数: {execution_result_from_algo.get('row_count', 0)}")
            logger.info(f"[步骤3/6]   本地执行行数: {local_execution_result.get('row_count', 0)}")
        else:
            step_validation["step3_sql_execution"]["status"] = "failed"
            step_validation["step3_sql_execution"]["details"] = {
                "error": execution_result_from_algo.get("error") if execution_result_from_algo else "未知错误",
                "local_success": local_success
            }
            logger.error(f"[步骤3/6] ✗ SQL执行失败")
            if execution_result_from_algo:
                logger.error(f"[步骤3/6]   错误: {execution_result_from_algo.get('error')}")
        
        # 步骤4: 图表配置生成验证
        logger.info("[步骤4/6] 图表配置生成验证...")
        chart_config = algorithm_result.get("chart_config")
        if chart_config:
            step_validation["step4_chart_config"]["status"] = "success"
            chart_type = chart_config.get("type", "unknown")
            step_validation["step4_chart_config"]["details"] = {
                "chart_type": chart_type,
                "has_config": bool(chart_config.get("config")),
                "has_render_data": bool(chart_config.get("render_data"))
            }
            logger.info(f"[步骤4/6] ✓ 图表配置生成成功")
            logger.info(f"[步骤4/6]   图表类型: {chart_type}")
        else:
            step_validation["step4_chart_config"]["status"] = "skipped"
            step_validation["step4_chart_config"]["details"] = {"reason": "未生成图表配置"}
            logger.info("[步骤4/6] - 未生成图表配置")
        
        # 步骤5: 结果总结验证
        logger.info("[步骤5/6] 结果总结验证...")
        summary = algorithm_result.get("summary")
        if summary:
            step_validation["step5_summary"]["status"] = "success"
            step_validation["step5_summary"]["details"] = {
                "summary_length": len(summary),
                "summary_preview": summary[:150] + "..." if len(summary) > 150 else summary
            }
            logger.info(f"[步骤5/6] ✓ 结果总结生成成功")
            logger.info(f"[步骤5/6]   总结长度: {len(summary)} 字符")
            logger.info(f"[步骤5/6]   总结预览: {summary[:100]}...")
        else:
            step_validation["step5_summary"]["status"] = "failed"
            step_validation["step5_summary"]["details"] = {"error": "未生成总结"}
            logger.error("[步骤5/6] ✗ 结果总结生成失败")
        
        # 步骤6: 推荐问题验证
        logger.info("[步骤6/6] 推荐问题生成验证...")
        recommendations = algorithm_result.get("recommendations", [])
        if recommendations and len(recommendations) > 0:
            step_validation["step6_recommendations"]["status"] = "success"
            step_validation["step6_recommendations"]["details"] = {
                "count": len(recommendations),
                "recommendations": recommendations[:3]  # 只记录前3个
            }
            logger.info(f"[步骤6/6] ✓ 推荐问题生成成功")
            logger.info(f"[步骤6/6]   推荐数量: {len(recommendations)}")
            for i, rec in enumerate(recommendations[:3], 1):
                logger.info(f"[步骤6/6]   推荐{i}: {rec[:80]}...")
        else:
            step_validation["step6_recommendations"]["status"] = "failed"
            step_validation["step6_recommendations"]["details"] = {"error": "未生成推荐问题"}
            logger.error("[步骤6/6] ✗ 推荐问题生成失败")
        
        # ========== 阶段4: 汇总测试结果 ==========
        logger.info("=" * 80)
        logger.info("[阶段4] 汇总测试结果")
        logger.info("=" * 80)
        
        # 计算成功步骤数
        success_steps = sum(1 for s in step_validation.values() if s["status"] == "success")
        total_steps = len(step_validation)
        
        # 计算总耗时
        total_time = int((datetime.now() - start_time).total_seconds() * 1000)
        
        # 判断整体测试是否成功（至少SQL生成、执行、总结成功）
        critical_steps = ["step1_sql_generation", "step3_sql_execution", "step5_summary"]
        all_critical_success = all(step_validation[s]["status"] == "success" for s in critical_steps)
        
        logger.info(f"[测试结果] 成功步骤: {success_steps}/{total_steps}")
        logger.info(f"[测试结果] 关键步骤: {'全部通过' if all_critical_success else '部分失败'}")
        logger.info(f"[测试结果] 总耗时: {total_time}ms")
        
        # 详细记录每个步骤状态
        for step_name, step_info in step_validation.items():
            status_icon = "✓" if step_info["status"] == "success" else "✗" if step_info["status"] == "failed" else "-"
            logger.info(f"[步骤状态] {status_icon} {step_name}: {step_info['status']}")
        
        logger.info("=" * 80)
        logger.info(f"[全流程测试完成] ID: {test_id}")
        logger.info("=" * 80)
        
        return {
            "success": all_critical_success,
            "test_id": test_id,
            "sql": algorithm_result["sql"],
            "filtered_sql": algorithm_result.get("filtered_sql"),
            "execution_result": local_execution_result if local_success else execution_result_from_algo,
            "chart_config": chart_config,
            "summary": summary,
            "recommendations": recommendations,
            "step_validation": step_validation,
            "steps": algorithm_result.get("steps", []),
            "statistics": {
                "success_steps": success_steps,
                "total_steps": total_steps,
                "success_rate": f"{success_steps}/{total_steps}",
                "total_time_ms": total_time
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[测试失败] ID: {test_id}, 错误: {e}")
        return {
            "success": False,
            "test_id": test_id,
            "error": str(e),
            "step_validation": step_validation
        }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "service": "test-framework-api"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
