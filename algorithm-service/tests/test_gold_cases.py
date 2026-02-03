"""
Gold测试用例测试脚本

从target_db/competition加载测试用例进行详细测试
Schema来源: finalTableSchema.xlsx (而非final.db)

用法:
    python test_gold_cases.py                 # 测试所有用例
    python test_gold_cases.py --limit 10      # 测试前10个用例
    python test_gold_cases.py --case-id 1     # 测试指定用例
    python test_gold_cases.py --level 1       # 测试指定难度
"""

import asyncio
import json
import logging
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from app.agent.text2sql.agent import Text2SqlAgent
from app.agent.text2sql.template.prompt_builder import PromptBuilder
from app.agent.text2sql.template.schema_formatter import format_schema_to_m_schema
from framework.request_builder import CompetitionRequestBuilder, ExcelSchemaLoader
from framework.validators import SQLSyntaxChecker, ExecutionValidator

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DetailedLogger:
    """详细日志记录器"""
    
    def __init__(self, case_id: int, question: str):
        self.case_id = case_id
        self.question = question
        self.logs = []
        
    def log(self, stage: str, message: str, data: Any = None):
        """记录日志"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "stage": stage,
            "message": message,
            "data": data
        }
        self.logs.append(log_entry)
        logger.info(f"[Case {self.case_id}] {stage}: {message}")
        
    def save(self, output_dir: Path):
        """保存日志"""
        output_file = output_dir / f"case_{self.case_id}_log.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                "case_id": self.case_id,
                "question": self.question,
                "logs": self.logs
            }, f, ensure_ascii=False, indent=2)


async def test_case(
    case: Dict[str, Any],
    verbose: bool = True,
    validate_execution: bool = True,
    include_related_tables: bool = True,
    include_all_tables: bool = False
) -> Dict[str, Any]:
    """
    测试单个用例
    
    Args:
        case: 测试用例数据
        verbose: 是否打印详细信息
        validate_execution: 是否验证SQL执行
        
    Returns:
        测试结果
    """
    case_id = case["id"]
    question = case["question"]
    expected_sql = case["sql"]
    expected_table = case.get("table", "")
    
    if verbose:
        print("\n" + "=" * 80)
        print(f"测试用例 #{case_id}: {question}")
        print("=" * 80)
    
    detailed_logger = DetailedLogger(case_id, question)
    detailed_logger.log("START", "开始测试")
    
    # 初始化组件
    agent = Text2SqlAgent()
    prompt_builder = PromptBuilder()
    syntax_checker = SQLSyntaxChecker()
    
    try:
        # 1. 从xlsx加载Schema（新方式）
        detailed_logger.log("SCHEMA", "从Excel加载Schema")
        schema_loader = ExcelSchemaLoader("target_db/competition/finalTableSchema.xlsx")
        
        # 根据配置加载表
        if include_all_tables:
            schema_data = schema_loader.load_schema()
            related_tables = schema_data["tables"]
            mode_desc = "所有表"
        elif include_related_tables:
            related_tables = schema_loader.get_related_tables(expected_table)
            mode_desc = "前缀匹配"
        else:
            # 只加载主表
            primary = schema_loader.get_table_schema(expected_table)
            related_tables = [primary] if primary else []
            mode_desc = "仅主表"
        
        if verbose:
            print(f"\n[Schema加载] 模式: {mode_desc}")
            print(f"  主表: {expected_table}")
            print(f"  加载表: {[t['name'] for t in related_tables]}")
        
        detailed_logger.log("SCHEMA", f"加载了 {len(related_tables)} 个表 (模式: {mode_desc})")
        
        # 2. 构建db_info（兼容原有格式）
        db_info = {}
        for table in related_tables:
            table_name = table["name"]
            fields = {}
            for field in table["fields"]:
                fields[field["name"]] = {
                    "type": field["type"],
                    "comment": field.get("comment", ""),
                }
            db_info[table_name] = {
                "columns": fields,
                "table_comment": table.get("comment", ""),
            }
        
        # 3. 格式化Schema
        detailed_logger.log("SCHEMA", "格式化Schema为M-Schema")
        schema_str = format_schema_to_m_schema(db_info, "final", "sqlite")
        
        if verbose:
            print(f"\n[M-Schema预览]")
            print(schema_str[:500] + "..." if len(schema_str) > 500 else schema_str)
        
        # 4. 构建Prompt
        detailed_logger.log("PROMPT", "构建Prompt")
        system_prompt, user_prompt = prompt_builder.build_sql_prompt(
            db_type="sqlite",
            schema=schema_str,
            question=question,
            engine="SQLite",
            terminologies="",
            data_training=""
        )
        prompt = f"{system_prompt}\n\n{user_prompt}"
        
        if verbose:
            print(f"\n[Prompt构建]")
            print(f"  长度: {len(prompt)} 字符")
        
        detailed_logger.log("PROMPT", f"Prompt长度: {len(prompt)}")
        
        # 5. 生成SQL
        detailed_logger.log("GENERATE", "生成SQL")
        
        if verbose:
            print(f"\n[SQL生成]")
        
        result = await agent.analyze(
            query=question,
            datasource_config={
                "db_type": "sqlite",
                "db_path": "target_db/competition/final.db"
            },
            schema_info={"tables": related_tables},
            terminologies=[],
            training_examples=[],
            permission_rules={},
            user_id=1
        )
        
        generated_sql = result.get("sql", "")
        
        if verbose:
            print(f"  生成SQL: {generated_sql[:100]}..." if len(generated_sql) > 100 else f"  生成SQL: {generated_sql}")
        
        detailed_logger.log("GENERATE", f"生成SQL: {generated_sql[:200]}")
        
        # 6. 语法检查
        detailed_logger.log("VALIDATE", "语法检查")
        syntax_result = syntax_checker.check(generated_sql)
        
        if verbose:
            print(f"\n[语法检查]")
            print(f"  通过: {syntax_result.valid}")
            if syntax_result.errors:
                print(f"  错误: {syntax_result.errors}")
            if syntax_result.warnings:
                print(f"  警告: {syntax_result.warnings}")
        
        detailed_logger.log("VALIDATE", f"语法检查结果: {syntax_result.valid}", {
            "valid": syntax_result.valid,
            "errors": syntax_result.errors,
            "warnings": syntax_result.warnings
        })
        
        # 7. 执行验证（可选）
        execution_result = None
        if validate_execution and generated_sql:
            detailed_logger.log("EXECUTE", "执行验证")
            
            validator = ExecutionValidator("target_db/competition/final.db")
            execution_result = validator.validate(generated_sql)
            
            if verbose:
                print(f"\n[执行验证]")
                print(f"  通过: {execution_result.valid}")
                print(f"  执行时间: {execution_result.details.get('execution_time_ms', 0)}ms")
                print(f"  返回行数: {execution_result.details.get('row_count', 0)}")
                if execution_result.errors:
                    print(f"  错误: {execution_result.errors}")
            
            detailed_logger.log("EXECUTE", f"执行结果: {execution_result.valid}", {
                "valid": execution_result.valid,
                "execution_time_ms": execution_result.details.get("execution_time_ms"),
                "row_count": execution_result.details.get("row_count")
            })
        
        # 8. 汇总结果
        test_result = {
            "case_id": case_id,
            "question": question,
            "expected_sql": expected_sql,
            "generated_sql": generated_sql,
            "success": bool(generated_sql),
            "syntax_valid": syntax_result.valid,
            "execution_valid": execution_result.valid if execution_result else None,
            "errors": syntax_result.errors + (execution_result.errors if execution_result else []),
            "warnings": syntax_result.warnings + (execution_result.warnings if execution_result else []),
            "details": {
                "schema_tables": [t["name"] for t in related_tables],
                "prompt_length": len(prompt),
                "execution_time_ms": execution_result.details.get("execution_time_ms") if execution_result else None,
                "row_count": execution_result.details.get("row_count") if execution_result else None
            }
        }
        
        detailed_logger.log("COMPLETE", "测试完成", test_result)
        
        if verbose:
            print(f"\n[测试结果]")
            print(f"  成功: {test_result['success']}")
            print(f"  语法正确: {test_result['syntax_valid']}")
            print(f"  执行成功: {test_result['execution_valid']}")
        
        return test_result
        
    except Exception as e:
        error_msg = str(e)
        detailed_logger.log("ERROR", f"测试失败: {error_msg}")
        
        if verbose:
            print(f"\n[错误]")
            print(f"  {error_msg}")
        
        import traceback
        traceback.print_exc()
        
        return {
            "case_id": case_id,
            "question": question,
            "expected_sql": expected_sql,
            "generated_sql": None,
            "success": False,
            "error": error_msg
        }


async def run_tests(
    limit: Optional[int] = None,
    case_id: Optional[int] = None,
    level: Optional[int] = None,
    output_dir: Optional[str] = None,
    validate_execution: bool = True,
    include_related_tables: bool = True,
    include_all_tables: bool = False
):
    """
    运行测试
    
    Args:
        limit: 限制测试数量
        case_id: 指定单个用例ID
        level: 指定难度级别
        output_dir: 输出目录
        validate_execution: 是否验证SQL执行
    """
    print("=" * 80)
    print("Gold测试用例测试")
    print("=" * 80)
    
    # 初始化Builder
    builder = CompetitionRequestBuilder("target_db/competition")
    
    # 加载统计信息
    stats = builder.get_statistics()
    print(f"\n测试数据统计:")
    print(f"  总用例数: {stats['total_cases']}")
    print(f"  难度分布: {stats['level_distribution']}")
    print(f"  Schema表数: {stats['schema_tables']}")
    
    # 加载用例
    all_cases = builder.load_all_gold_cases()
    
    # 筛选用例
    if case_id:
        cases = [c for c in all_cases if c["id"] == case_id]
    elif level:
        cases = [c for c in all_cases if c.get("level") == level]
    else:
        cases = all_cases
    
    if limit:
        cases = cases[:limit]
    
    print(f"\n本次测试: {len(cases)} 个用例")
    print("-" * 80)
    
    # 创建输出目录
    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
    else:
        output_path = Path(__file__).parent / "test_outputs"
        output_path.mkdir(exist_ok=True)
    
    # 执行测试
    results = []
    passed = 0
    failed = 0
    
    for i, case in enumerate(cases, 1):
        print(f"\n[{i}/{len(cases)}] ", end="")
        
        result = await test_case(
            case,
            verbose=False,  # 批量测试时不打印详细信息
            validate_execution=validate_execution,
            include_related_tables=include_related_tables,
            include_all_tables=include_all_tables
        )
        
        results.append(result)
        
        if result["success"]:
            print(f"✓ Case #{case['id']}: 通过")
            passed += 1
        else:
            print(f"✗ Case #{case['id']}: 失败 - {result.get('error', '未知错误')}")
            failed += 1
    
    # 打印汇总
    print("\n" + "=" * 80)
    print("测试汇总")
    print("=" * 80)
    print(f"总计: {len(cases)}")
    print(f"通过: {passed}")
    print(f"失败: {failed}")
    print(f"成功率: {passed/len(cases)*100:.1f}%" if cases else "N/A")
    
    # 按难度统计
    level_stats = {}
    for result in results:
        case = next((c for c in cases if c["id"] == result["case_id"]), None)
        if case:
            level = case.get("level", 0)
            if level not in level_stats:
                level_stats[level] = {"total": 0, "passed": 0}
            level_stats[level]["total"] += 1
            if result["success"]:
                level_stats[level]["passed"] += 1
    
    print("\n按难度统计:")
    for level in sorted(level_stats.keys()):
        stats = level_stats[level]
        rate = stats["passed"] / stats["total"] * 100 if stats["total"] > 0 else 0
        print(f"  Level {level}: {stats['passed']}/{stats['total']} ({rate:.1f}%)")
    
    # 保存结果
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = output_path / f"test_results_{timestamp}.json"
    
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump({
            "timestamp": timestamp,
            "total": len(cases),
            "passed": passed,
            "failed": failed,
            "level_stats": level_stats,
            "results": results
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n结果已保存: {result_file}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Gold测试用例测试",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python test_gold_cases.py --limit 10
  python test_gold_cases.py --case-id 1
  python test_gold_cases.py --level 1
  python test_gold_cases.py --no-execution  # 不验证SQL执行
  python test_gold_cases.py --schema-mode all  # 加载所有表
        """
    )
    
    parser.add_argument("--limit", type=int, help="限制测试数量")
    parser.add_argument("--case-id", type=int, help="指定测试用例ID")
    parser.add_argument("--level", type=int, choices=[1, 2, 3], help="指定难度级别")
    parser.add_argument("--output-dir", type=str, help="输出目录")
    parser.add_argument("--no-execution", action="store_true", help="不验证SQL执行")
    parser.add_argument("--schema-mode", type=str, choices=["primary", "related", "all"],
                       default="related", help="Schema加载模式: primary=只主表, related=前缀匹配(默认), all=所有表")
    
    args = parser.parse_args()
    
    # 根据schema-mode设置参数
    include_related = args.schema_mode == "related"
    include_all = args.schema_mode == "all"
    
    asyncio.run(run_tests(
        limit=args.limit,
        case_id=args.case_id,
        level=args.level,
        output_dir=args.output_dir,
        validate_execution=not args.no_execution,
        include_related_tables=include_related,
        include_all_tables=include_all
    ))


if __name__ == "__main__":
    main()
