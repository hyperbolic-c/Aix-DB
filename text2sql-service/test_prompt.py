"""
测试提示词构建
验证提示词是否正确构建
"""

import asyncio
import sys
sys.path.insert(0, '/Users/liam/LLMPro/Aix-DB/text2sql-service')

from app.generator.prompt_builder import PromptBuilder
from app.template.schema_formatter import format_schema_to_m_schema, get_database_engine_info


def test_prompt_building():
    """测试提示词构建"""
    
    # 构建测试数据
    tables = [
        {
            "name": "orders",
            "comment": "订单表",
            "columns": [
                {"name": "id", "type": "bigint", "comment": "订单ID", "is_primary": True},
                {"name": "user_id", "type": "bigint", "comment": "用户ID"},
                {"name": "status", "type": "varchar", "comment": "订单状态"},
                {"name": "total_amount", "type": "decimal", "comment": "订单总金额"},
                {"name": "created_at", "type": "datetime", "comment": "创建时间"}
            ]
        }
    ]
    
    # 格式化 Schema
    schema_str = format_schema_to_m_schema(
        db_info={t["name"]: t for t in tables},
        db_name="ecommerce",
        db_type="mysql"
    )
    
    print("=" * 80)
    print("M-Schema 格式:")
    print("=" * 80)
    print(schema_str)
    print()
    
    # 构建提示词
    builder = PromptBuilder()
    
    chat_history = [
        {"role": "user", "content": "查询最近7天的订单"},
        {"role": "assistant", "content": "已为您查询", "sql": "SELECT * FROM orders WHERE created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY) LIMIT 40"}
    ]
    
    system_prompt, user_prompt = builder.build_sql_prompt(
        db_type="mysql",
        schema=schema_str,
        question="按状态统计订单数量",
        engine=get_database_engine_info("mysql"),
        chat_history=chat_history,
        terminologies="订单状态包括：pending(待处理)、paid(已支付)、completed(已完成)",
        training_examples="",
        error_msg="",
        current_time="2026-02-27 10:00:00",
        enable_query_limit=True,
        change_title=False,
        lang="简体中文"
    )
    
    print("=" * 80)
    print("系统提示词 (前1000字符):")
    print("=" * 80)
    print(system_prompt[:1000])
    print("...")
    print()
    
    print("=" * 80)
    print("用户提示词:")
    print("=" * 80)
    print(user_prompt)
    print()
    
    # 验证关键内容
    print("=" * 80)
    print("验证提示词内容:")
    print("=" * 80)
    
    checks = [
        ("数据库引擎", "MySQL 8.0" in system_prompt),
        ("M-Schema", "【DB_ID】" in system_prompt),
        ("表结构", "orders" in system_prompt),
        ("对话历史", "对话历史" in user_prompt or "用户:" in user_prompt),
        ("当前时间", "2026-02-27" in user_prompt),
        ("数据量限制规则", "query_limit" in system_prompt.lower() or "LIMIT" in system_prompt),
    ]
    
    for name, result in checks:
        status = "✅" if result else "❌"
        print(f"{status} {name}: {'通过' if result else '未通过'}")
    
    return all(r for _, r in checks)


if __name__ == "__main__":
    success = test_prompt_building()
    print()
    print("=" * 80)
    if success:
        print("✅ 所有测试通过！提示词构建正常。")
    else:
        print("❌ 部分测试未通过，请检查提示词构建逻辑。")
    print("=" * 80)
