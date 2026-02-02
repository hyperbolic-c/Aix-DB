"""
从SQLite数据库提取Schema信息
用于生成测试数据或初始化
"""

import sqlite3
import json
import sys
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import SQLiteExecutor


def extract_schema(db_path: str, output_path: str = None):
    """
    提取数据库Schema到JSON文件
    
    Args:
        db_path: SQLite数据库文件路径
        output_path: 输出JSON文件路径
    """
    print(f"正在提取数据库Schema: {db_path}")
    
    # 使用SQLiteExecutor获取Schema
    executor = SQLiteExecutor(db_path)
    
    # 测试连接
    if not executor.test_connection():
        print("数据库连接失败!")
        return None
    
    # 获取Schema信息
    schema_info = executor.get_schema_info()
    
    # 获取每张表的样例数据
    for table in schema_info["tables"]:
        table_name = table["name"]
        sample_data = executor.get_table_sample(table_name, limit=3)
        table["sample_data"] = sample_data
        print(f"  ✓ {table_name}: {len(table['fields'])} 个字段, {len(sample_data)} 条样例")
    
    # 保存到文件
    if output_path:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(schema_info, f, indent=2, ensure_ascii=False)
        
        print(f"\nSchema已保存到: {output_file}")
    
    return schema_info


def print_schema_summary(schema_info: dict):
    """打印Schema摘要"""
    print("\n" + "=" * 60)
    print("数据库Schema摘要")
    print("=" * 60)
    
    tables = schema_info.get("tables", [])
    print(f"\n共 {len(tables)} 张表:\n")
    
    for table in tables:
        print(f"  📋 {table['name']}")
        print(f"     说明: {table.get('comment', 'N/A')}")
        print(f"     字段数: {len(table.get('fields', []))}")
        
        # 打印字段列表
        fields = table.get("fields", [])
        if fields:
            print(f"     字段: {', '.join([f['name'] for f in fields[:5]])}", end="")
            if len(fields) > 5:
                print(f" ... 等{len(fields)}个字段")
            else:
                print()
        
        # 打印样例数据
        sample_data = table.get("sample_data", [])
        if sample_data:
            print(f"     样例: {len(sample_data)} 条")
        
        print()


def generate_test_request(db_path: str, output_path: str = None):
    """
    生成测试请求JSON
    
    Args:
        db_path: SQLite数据库文件路径
        output_path: 输出JSON文件路径
    """
    schema_info = extract_schema(db_path)
    
    if not schema_info:
        return None
    
    # 构建测试请求
    test_request = {
        "query": "查询最近7天的工单总量",
        "datasource_config": {
            "db_type": "sqlite",
            "host": "",
            "port": 0,
            "database": db_path,
            "username": "",
            "password": ""
        },
        "schema_info": schema_info,
        "terminologies": [
            {"word": "工单", "description": "用户提交的诉求单"},
            {"word": "办结", "description": "工单处理完成"},
            {"word": "满意度", "description": "用户对处理结果的评价"},
            {"word": "专题", "description": "特定主题的工单分类，如营商环境、疫情防控"},
            {"word": "逾期", "description": "超过规定时间未办结的工单"},
            {"word": "回访", "description": "对工单处理结果进行电话回访"}
        ],
        "training_examples": [
            {
                "question": "查询昨天的工单量",
                "sql": "SELECT SUM(item_num) FROM items_total_day WHERE busi_time = DATE('now', '-1 day')",
                "description": "查询昨天所有工单的总数量"
            },
            {
                "question": "最近7天各地区工单量排名",
                "sql": "SELECT area, SUM(order_cnt) as total FROM sub_area_total_day WHERE busi_time >= DATE('now', '-7 days') GROUP BY area ORDER BY total DESC",
                "description": "统计最近7天各地区的工单量并排序"
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
    
    # 保存到文件
    if output_path:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(test_request, f, indent=2, ensure_ascii=False)
        
        print(f"\n测试请求已保存到: {output_file}")
    
    return test_request


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="SQLite数据库Schema提取工具")
    parser.add_argument("--db", default="/Users/liam/LLMPro/Aix-DB/target_db/competition/final.db",
                        help="SQLite数据库文件路径")
    parser.add_argument("--output", "-o", default="/Users/liam/LLMPro/Aix-DB/algorithm-service/data/schema.json",
                        help="输出Schema JSON文件路径")
    parser.add_argument("--test-request", "-t", action="store_true",
                        help="生成测试请求JSON")
    parser.add_argument("--summary", "-s", action="store_true",
                        help="打印Schema摘要")
    
    args = parser.parse_args()
    
    if args.test_request:
        # 生成测试请求
        test_output = args.output.replace("schema.json", "test_request.json")
        test_request = generate_test_request(args.db, test_output)
        if test_request:
            print("\n测试请求生成成功!")
    else:
        # 提取Schema
        schema_info = extract_schema(args.db, args.output)
        
        if schema_info:
            print("\nSchema提取成功!")
            
            if args.summary:
                print_schema_summary(schema_info)
