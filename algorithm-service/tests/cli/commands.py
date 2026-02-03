"""
CLI命令处理器

实现各种测试命令的处理逻辑
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime

# 添加路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from framework.request_builder import CompetitionRequestBuilder
from framework.validators import SQLSyntaxChecker, ExecutionValidator
from stream_processor import StreamProcessor


class CommandHandler:
    """命令处理器"""
    
    def __init__(self):
        self.base_url = "http://localhost:8001"
        self.request_builder: Optional[CompetitionRequestBuilder] = None
        self.syntax_checker = SQLSyntaxChecker()
        
    def set_base_url(self, url: str):
        """设置服务地址"""
        self.base_url = url
        print(f"✓ 服务地址已设置为: {url}")
        
    def load_competition(self):
        """加载competition测试数据"""
        print("加载测试数据: target_db/competition")
        
        try:
            self.request_builder = CompetitionRequestBuilder("target_db/competition")
            stats = self.request_builder.get_statistics()
            
            print(f"✓ 加载 gold.jsonl: {stats['total_cases']} 个测试用例")
            print(f"✓ 加载 finalTableSchema.xlsx: {stats['schema_tables']} 张表")
            print(f"  难度分布: {stats['level_distribution']}")
            print(f"✓ 加载 fixtures: 预置术语和SQL示例")
            
        except FileNotFoundError as e:
            print(f"✗ 文件不存在: {e}")
            print("  请确保 target_db/competition 目录存在")
        except Exception as e:
            print(f"✗ 加载失败: {e}")
            
    def show_fixtures(self):
        """显示预置的测试数据"""
        from fixtures import load_terminologies, load_sql_examples
        
        print("\n预置测试数据:")
        print("-" * 60)
        
        terminologies = load_terminologies()
        print(f"\n术语 ({len(terminologies)} 个):")
        for t in terminologies[:10]:  # 显示前10个
            print(f"  - {t['term']}: {t['description'][:50]}...")
        if len(terminologies) > 10:
            print(f"  ... 还有 {len(terminologies) - 10} 个")
            
        examples = load_sql_examples()
        print(f"\nSQL示例 ({len(examples)} 个):")
        for e in examples[:5]:  # 显示前5个
            print(f"  - {e['question'][:40]}...")
        if len(examples) > 5:
            print(f"  ... 还有 {len(examples) - 5} 个")
            
    def show_case(self, case_id: int):
        """显示测试用例详情"""
        if not self.request_builder:
            print("请先运行 load-competition")
            return
            
        case_info = self.request_builder.get_case_info(case_id)
        if not case_info:
            print(f"找不到测试用例 #{case_id}")
            return
            
        print(f"\n测试用例 #{case_id}:")
        print("-" * 60)
        print(f"问题: {case_info['question']}")
        print(f"主表: {case_info['table']}")
        print(f"难度: Level {case_info['level']}")
        print(f"参考SQL: {case_info['reference_sql'][:100]}...")
        
    def inspect_case(self, case_id: int):
        """检查测试用例的请求构建"""
        if not self.request_builder:
            print("请先运行 load-competition")
            return
            
        try:
            request = self.request_builder.build_request(case_id)
            case_info = self.request_builder.get_case_info(case_id)
            
            print(f"\n测试用例 #{case_id} 请求详情:")
            print("=" * 60)
            
            print(f"\n[问题]")
            print(f"  {case_info['question']}")
            
            print(f"\n[Schema信息]")
            schema_info = request['schema_info']
            for table in schema_info['tables']:
                print(f"  表: {table['name']}")
                print(f"    字段: {len(table['fields'])} 个")
                for field in table['fields'][:5]:
                    print(f"      - {field['name']} ({field['type']})")
                if len(table['fields']) > 5:
                    print(f"      ... 还有 {len(table['fields']) - 5} 个字段")
                    
            print(f"\n[请求体大小]")
            request_json = json.dumps(request, ensure_ascii=False)
            print(f"  JSON大小: {len(request_json)} 字符")
            
        except Exception as e:
            print(f"检查失败: {e}")
            
    async def test_case(self, case_id: int):
        """运行单个测试用例"""
        if not self.request_builder:
            print("请先运行 load-competition")
            return
            
        try:
            request = self.request_builder.build_request(case_id)
            case_info = self.request_builder.get_case_info(case_id)
            
            print(f"\n运行测试: Case #{case_id}")
            print("=" * 60)
            print(f"问题: {case_info['question']}")
            print(f"Schema表: {[t['name'] for t in request['schema_info']['tables']]}")
            
            # 发送请求
            print(f"\n[发送请求]")
            print(f"POST {self.base_url}/api/v1/analyze")
            
            processor = StreamProcessor(verbose=True, use_colors=True)
            
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/v1/analyze",
                    json=request,
                    timeout=60.0
                ) as response:
                    print(f"状态码: {response.status_code}")
                    result = await processor.process(response.aiter_lines())
                    
            processor.print_final_report()
            
            # 验证生成的SQL
            if result and result.sql:
                print(f"\n[SQL验证]")
                syntax_result = self.syntax_checker.check(result.sql)
                print(f"  语法检查: {'通过' if syntax_result.valid else '失败'}")
                if syntax_result.errors:
                    print(f"  错误: {syntax_result.errors}")
                    
                # 执行验证
                validator = ExecutionValidator("target_db/competition/final.db")
                exec_result = validator.validate(result.sql)
                print(f"  执行检查: {'通过' if exec_result.valid else '失败'}")
                if exec_result.valid:
                    print(f"  返回行数: {exec_result.details['row_count']}")
                    print(f"  执行时间: {exec_result.details['execution_time_ms']}ms")
                    
        except Exception as e:
            print(f"测试失败: {e}")
            import traceback
            traceback.print_exc()
            
    async def test_custom(self, question: str):
        """使用自定义问题测试"""
        if not self.request_builder:
            print("请先运行 load-competition")
            return
            
        try:
            request = self.request_builder.build_request_by_question(question)
            
            print(f"\n自定义问题测试:")
            print("=" * 60)
            print(f"问题: {question}")
            print(f"Schema表: {[t['name'] for t in request['schema_info']['tables']]}")
            
            processor = StreamProcessor(verbose=True, use_colors=True)
            
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/v1/analyze",
                    json=request,
                    timeout=60.0
                ) as response:
                    result = await processor.process(response.aiter_lines())
                    
            processor.print_final_report()
            
        except Exception as e:
            print(f"测试失败: {e}")
            
    async def test_suite(self, level: int = None, limit: int = None):
        """运行测试套件"""
        if not self.request_builder:
            print("请先运行 load-competition")
            return
            
        cases = self.request_builder.load_all_gold_cases()
        
        if level:
            cases = [c for c in cases if c.get("level") == level]
            print(f"\n运行 Level {level} 测试套件")
        else:
            print("\n运行完整测试套件")
            
        if limit:
            cases = cases[:limit]
            
        print(f"共 {len(cases)} 个测试用例")
        print("-" * 60)
        
        passed = 0
        failed = 0
        
        for i, case in enumerate(cases, 1):
            print(f"\n[{i}/{len(cases)}] Case #{case['id']}")
            print(f"问题: {case['question'][:50]}...")
            
            try:
                request = self.request_builder.build_request(case['id'])
                
                processor = StreamProcessor(verbose=False, use_colors=False)
                
                async with httpx.AsyncClient() as client:
                    async with client.stream(
                        "POST",
                        f"{self.base_url}/api/v1/analyze",
                        json=request,
                        timeout=60.0
                    ) as response:
                        result = await processor.process(response.aiter_lines())
                        
                if result and result.sql:
                    print(f"✓ 生成SQL成功")
                    passed += 1
                else:
                    print(f"✗ 生成SQL失败")
                    failed += 1
                    
            except Exception as e:
                print(f"✗ 错误: {e}")
                failed += 1
                
        print("\n" + "=" * 60)
        print("测试汇总")
        print("=" * 60)
        print(f"总计: {len(cases)}")
        print(f"通过: {passed}")
        print(f"失败: {failed}")
        print(f"成功率: {passed/len(cases)*100:.1f}%" if cases else "N/A")
        
    def show_help(self):
        """显示帮助信息"""
        print("""
算法测试 CLI
============

可用命令:
  connect <url>           连接到算法服务 (默认: http://localhost:8001)
  load-competition        加载target_db/competition测试数据
  fixtures                查看预置的测试数据
  case <id>               查看测试用例详情
  inspect <id>            检查测试用例的请求构建
  test <id>               运行指定测试用例
  test-custom "问题"       使用自定义问题测试
  test-suite [level]      运行测试套件 (可指定level: 1/2/3)
  help                    显示帮助信息
  exit                    退出

示例:
  > connect http://localhost:8001
  > load-competition
  > test 1
  > test-suite --level 1
  > test-custom "查询昨天的订单量"
        """)
