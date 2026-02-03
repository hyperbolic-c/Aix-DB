"""
SQLite数据库测试脚本
用于测试算法服务对final.db的查询能力
"""

import asyncio
import json
import sys
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from stream_processor import StreamProcessor, ProcessResult


# 加载测试请求
TEST_REQUEST_PATH = Path(__file__).parent.parent / "data" / "test_request.json"


def load_test_request() -> dict:
    """加载测试请求数据"""
    if TEST_REQUEST_PATH.exists():
        with open(TEST_REQUEST_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        print(f"警告: 测试请求文件不存在: {TEST_REQUEST_PATH}")
        print("请先运行: python tools/extract_schema.py --test-request")
        return None


async def test_sqlite_query(query: str, base_url: str = "http://localhost:8002"):
    """
    测试SQLite查询
    
    Args:
        query: 用户问题
        base_url: 算法服务地址
    """
    print("=" * 60)
    print(f"测试查询: {query}")
    print("=" * 60)
    
    # 加载测试请求模板
    request_data = load_test_request()
    if not request_data:
        return None
    
    # 更新查询问题
    request_data["query"] = query
    
    # 创建流式处理器
    processor = StreamProcessor(verbose=True, use_colors=True)
    
    try:
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{base_url}/api/v1/analyze",
                json=request_data,
                timeout=60.0
            ) as response:
                print(f"状态码: {response.status_code}")
                print("-" * 60)
                
                # 处理流式响应
                result: ProcessResult = await processor.process(response.aiter_lines())
        
        # 打印最终报告
        processor.print_final_report()
        
        return result
        
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_health(base_url: str = "http://localhost:8002"):
    """测试健康检查"""
    print("=" * 60)
    print("测试健康检查")
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


async def run_test_cases(base_url: str = "http://localhost:8002"):
    """运行测试用例"""
    
    # 测试用例列表
    test_cases = [
        "查询最近7天的工单总量",
        "查询昨天的工单量",
        "最近7天各地区工单量排名",
        "查询呼叫接通情况",
        "查询各工单类型的数量",
        "查询专题受理情况",
    ]
    
    print("\n" + "=" * 60)
    print("运行测试用例")
    print("=" * 60)
    
    results = []
    for i, query in enumerate(test_cases, 1):
        print(f"\n[{i}/{len(test_cases)}] ", end="")
        result = await test_sqlite_query(query, base_url)
        results.append({"query": query, "success": result is not None})
        
        # 每个测试之间暂停一下
        if i < len(test_cases):
            await asyncio.sleep(1)
    
    # 打印测试摘要
    print("\n" + "=" * 60)
    print("测试摘要")
    print("=" * 60)
    
    success_count = sum(1 for r in results if r["success"])
    print(f"\n通过: {success_count}/{len(results)}")
    
    for r in results:
        status = "✓" if r["success"] else "✗"
        print(f"  {status} {r['query']}")


def print_usage():
    """打印使用说明"""
    print("""
SQLite数据库测试脚本

用法:
    python test_sqlite.py [选项] [问题]

选项:
    health              测试健康检查接口
    query "问题"        使用自定义问题测试
    cases               运行预设测试用例
    
示例:
    python test_sqlite.py health
    python test_sqlite.py query "查询最近7天的工单总量"
    python test_sqlite.py cases

服务地址:
    默认: http://localhost:8002
    可通过环境变量 ALGO_SERVICE_URL 修改
""")


async def main():
    """主函数"""
    import os
    
    # 获取服务地址
    base_url = os.getenv("ALGO_SERVICE_URL", "http://localhost:8002")
    
    # 解析命令行参数
    args = sys.argv[1:]
    
    if not args:
        print_usage()
        return
    
    if args[0] == "health":
        await test_health(base_url)
        
    elif args[0] == "query" and len(args) >= 2:
        query = args[1]
        await test_sqlite_query(query, base_url)
        
    elif args[0] == "cases":
        # 先测试健康检查
        health_ok = await test_health(base_url)
        if not health_ok:
            print("\n健康检查失败，请确保服务已启动:")
            print(f"  cd algorithm-service")
            print(f"  python -m app.main")
            return
        
        await run_test_cases(base_url)
        
    elif args[0] in ("-h", "--help", "help"):
        print_usage()
        
    else:
        print(f"未知选项: {args[0]}")
        print_usage()


if __name__ == "__main__":
    asyncio.run(main())
