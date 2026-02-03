"""
算法服务API测试脚本

支持两种测试模式:
1. 标准测试: 使用预定义请求模板
2. Gold用例测试: 从target_db/competition加载测试用例

用法:
    python test_api.py                    # 运行标准测试
    python test_api.py --gold             # 运行Gold用例测试
    python test_api.py --gold --case-id 1 # 测试指定用例
    python test_api.py --gold --limit 10  # 测试前10个用例
    python test_api.py --gold --level 1   # 测试指定难度的用例
"""

import asyncio
import json
import sys
import argparse
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

import httpx
from stream_processor import StreamProcessor, ProcessResult
from framework.request_builder import CompetitionRequestBuilder


# 标准测试请求数据（用于快速测试）
TEST_REQUEST = {
    "query": "查询最近7天的订单量",
    "datasource_config": {
        "db_type": "mysql",
        "host": "localhost",
        "port": 3306,
        "database": "test_db",
        "username": "root",
        "password": "password"
    },
    "schema_info": {
        "tables": [
            {
                "name": "orders",
                "comment": "订单表",
                "fields": [
                    {"name": "id", "type": "bigint", "comment": "订单ID", "is_primary": True},
                    {"name": "order_date", "type": "datetime", "comment": "订单日期"},
                    {"name": "amount", "type": "decimal(10,2)", "comment": "订单金额"},
                    {"name": "user_id", "type": "bigint", "comment": "用户ID"}
                ],
                "foreign_keys": [
                    {"column": "user_id", "ref_table": "users", "ref_column": "id"}
                ]
            },
            {
                "name": "users",
                "comment": "用户表",
                "fields": [
                    {"name": "id", "type": "bigint", "comment": "用户ID", "is_primary": True},
                    {"name": "username", "type": "varchar(100)", "comment": "用户名"},
                    {"name": "email", "type": "varchar(200)", "comment": "邮箱"}
                ]
            }
        ],
        "relationships": [
            {"table1": "orders", "table2": "users", "type": "many_to_one"}
        ]
    },
    "terminologies": [
        {"word": "订单量", "description": "订单的数量，使用COUNT(*)统计"},
        {"word": "最近7天", "description": "当前时间往前推7天，使用DATE_SUB(NOW(), INTERVAL 7 DAY)"},
        {"word": "销售额", "description": "订单金额的总和，使用SUM(amount)"}
    ],
    "training_examples": [
        {
            "question": "查询昨天的销售额",
            "sql": "SELECT SUM(amount) FROM orders WHERE DATE(order_date) = DATE_SUB(CURDATE(), INTERVAL 1 DAY)",
            "description": "查询昨天所有订单的总金额"
        },
        {
            "question": "查询每个用户的订单数量",
            "sql": "SELECT user_id, COUNT(*) as order_count FROM orders GROUP BY user_id",
            "description": "按用户统计订单数量"
        }
    ],
    "permission_rules": {
        "row_filters": [],
        "column_permissions": {}
    },
    "chat_history": [],
    "user_id": 1,
    "datasource_id": 1
}


async def test_health_check(base_url: str = "http://localhost:8001"):
    """测试健康检查接口"""
    print("=" * 60)
    print("测试健康检查接口")
    print("=" * 60)
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{base_url}/api/v1/health", timeout=5.0)
            print(f"状态码: {response.status_code}")
            print(f"响应: {response.json()}")
            return response.status_code == 200
        except Exception as e:
            print(f"健康检查失败: {e}")
            return False


async def test_analyze(base_url: str = "http://localhost:8001"):
    """测试Text2SQL分析接口（标准测试）"""
    print("\n" + "=" * 60)
    print("测试Text2SQL分析接口（标准测试）")
    print("=" * 60)
    
    # 创建流式处理器
    processor = StreamProcessor(verbose=True, use_colors=True)
    
    try:
        async with httpx.AsyncClient() as client:
            async with client.stream(
                    "POST",
                    f"{base_url}/api/v1/analyze",
                    json=TEST_REQUEST,
                    timeout=60.0
                ) as response:
                print(f"状态码: {response.status_code}")
                print(f"内容类型: {response.headers.get('content-type', 'unknown')}")
                print("-" * 60)
                
                # 处理流式响应
                result: ProcessResult = await processor.process(response.aiter_lines())
        
        # 打印最终报告
        processor.print_final_report()
        
        # 保存结果到文件
        result_file = Path(__file__).parent / "test_result.json"
        processor.save_result(str(result_file))
        
        return result
        
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_gold_case(
    case_id: int,
    base_url: str = "http://localhost:8001",
    verbose: bool = True
) -> ProcessResult:
    """
    测试单个Gold用例
    
    Args:
        case_id: 测试用例ID
        base_url: 服务地址
        verbose: 是否打印详细信息
        
    Returns:
        处理结果
    """
    if verbose:
        print("\n" + "=" * 60)
        print(f"测试Gold用例 #{case_id}")
        print("=" * 60)
    
    # 使用RequestBuilder构建请求
    builder = CompetitionRequestBuilder("target_db/competition")
    
    try:
        request_data = builder.build_request(case_id)
    except ValueError as e:
        print(f"构建请求失败: {e}")
        return None
    except FileNotFoundError as e:
        print(f"文件不存在: {e}")
        print("请确保target_db/competition目录存在")
        return None
    
    if verbose:
        case_info = builder.get_case_info(case_id)
        print(f"\n问题: {case_info.get('question', '')}")
        print(f"主表: {case_info.get('table', '')}")
        print(f"难度: Level {case_info.get('level', 0)}")
        print(f"Schema表: {[t['name'] for t in request_data['schema_info']['tables']]}")
    
    # 创建流式处理器
    processor = StreamProcessor(verbose=verbose, use_colors=True)
    
    try:
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{base_url}/api/v1/analyze",
                json=request_data,
                timeout=60.0
            ) as response:
                if verbose:
                    print(f"\n状态码: {response.status_code}")
                
                # 处理流式响应
                result: ProcessResult = await processor.process(response.aiter_lines())
        
        if verbose:
            # 打印最终报告
            processor.print_final_report()
        
        return result
        
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_gold_cases(
    limit: int = None,
    level: int = None,
    case_id: int = None,
    base_url: str = "http://localhost:8001"
):
    """
    批量测试Gold用例
    
    Args:
        limit: 限制测试数量
        level: 指定难度级别
        case_id: 指定单个用例ID
        base_url: 服务地址
    """
    print("=" * 60)
    print("Gold用例批量测试")
    print("=" * 60)
    
    # 初始化Builder
    builder = CompetitionRequestBuilder("target_db/competition")
    
    # 加载所有用例
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
    
    print(f"\n总计 {len(cases)} 个测试用例")
    print(f"服务地址: {base_url}")
    print("-" * 60)
    
    # 执行测试
    results = []
    passed = 0
    failed = 0
    
    for i, case in enumerate(cases, 1):
        print(f"\n[{i}/{len(cases)}] 测试用例 #{case['id']}")
        print(f"问题: {case['question'][:50]}...")
        
        result = await test_gold_case(case["id"], base_url, verbose=False)
        
        if result and result.sql:
            print(f"✓ 生成SQL成功")
            passed += 1
        else:
            print(f"✗ 生成SQL失败")
            failed += 1
        
        results.append({
            "case_id": case["id"],
            "question": case["question"],
            "success": result is not None and result.sql is not None,
            "sql": result.sql if result else None
        })
    
    # 打印汇总
    print("\n" + "=" * 60)
    print("测试汇总")
    print("=" * 60)
    print(f"总计: {len(cases)}")
    print(f"通过: {passed}")
    print(f"失败: {failed}")
    print(f"成功率: {passed/len(cases)*100:.1f}%" if cases else "N/A")
    
    # 保存结果
    output_file = Path(__file__).parent / "gold_test_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "total": len(cases),
            "passed": passed,
            "failed": failed,
            "results": results
        }, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存: {output_file}")


async def test_with_custom_query(query: str, base_url: str = "http://localhost:8001"):
    """使用自定义问题测试"""
    print("\n" + "=" * 60)
    print(f"自定义问题测试: {query}")
    print("=" * 60)
    
    # 使用Builder构建请求
    builder = CompetitionRequestBuilder("target_db/competition")
    request_data = builder.build_request_by_question(query)
    
    processor = StreamProcessor(verbose=True, use_colors=True)
    
    try:
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{base_url}/api/v1/analyze",
                json=request_data,
                timeout=60.0
            ) as response:
                result: ProcessResult = await processor.process(response.aiter_lines())
        
        processor.print_final_report()
        return result
        
    except Exception as e:
        print(f"\n测试失败: {e}")
        return None


def print_usage():
    """打印使用说明"""
    print("""
算法服务API测试脚本

用法:
    python test_api.py [选项]

选项:
    --gold                  运行Gold用例测试
    --case-id ID            指定测试用例ID
    --limit N               限制测试数量
    --level N               指定难度级别(1/2/3)
    --custom "问题"          使用自定义问题测试
    health                  测试健康检查接口
    analyze                 测试Text2SQL分析接口(默认)
    
示例:
    # 标准测试
    python test_api.py
    
    # Gold用例测试
    python test_api.py --gold
    python test_api.py --gold --case-id 1
    python test_api.py --gold --limit 10
    python test_api.py --gold --level 1
    
    # 自定义问题
    python test_api.py --custom "查询订单总额"

服务地址:
    默认: http://localhost:8001
    可通过环境变量 ALGO_SERVICE_URL 修改
""")


async def main():
    """主函数"""
    import os
    
    # 获取服务地址
    base_url = os.getenv("ALGO_SERVICE_URL", "http://localhost:8001")
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description="算法服务API测试",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python test_api.py --gold --limit 10
  python test_api.py --gold --case-id 1
  python test_api.py --custom "查询订单总额"
        """
    )
    
    parser.add_argument("--gold", action="store_true", help="运行Gold用例测试")
    parser.add_argument("--case-id", type=int, help="指定测试用例ID")
    parser.add_argument("--limit", type=int, help="限制测试数量")
    parser.add_argument("--level", type=int, choices=[1, 2, 3], help="指定难度级别")
    parser.add_argument("--custom", type=str, help="自定义问题")
    parser.add_argument("--url", type=str, default=base_url, help="服务地址")
    
    args = parser.parse_args()
    
    if args.gold:
        # Gold用例测试
        if args.case_id:
            # 单个用例
            health_ok = await test_health_check(args.url)
            if not health_ok:
                print("\n健康检查失败，请确保服务已启动")
                return
            
            result = await test_gold_case(args.case_id, args.url)
            if result:
                print("\n测试完成!")
        else:
            # 批量测试
            await test_gold_cases(
                limit=args.limit,
                level=args.level,
                base_url=args.url
            )
    
    elif args.custom:
        # 自定义问题测试
        health_ok = await test_health_check(args.url)
        if not health_ok:
            print("\n健康检查失败，请确保服务已启动")
            return
        
        result = await test_with_custom_query(args.custom, args.url)
        if result:
            print("\n测试完成!")
    
    else:
        # 默认标准测试
        health_ok = await test_health_check(args.url)
        if not health_ok:
            print("\n健康检查失败，请确保服务已启动:")
            print(f"  cd algorithm-service")
            print(f"  python -m app.main")
            return
        
        result = await test_analyze(args.url)
        if result:
            print("\n测试完成!")


if __name__ == "__main__":
    asyncio.run(main())
