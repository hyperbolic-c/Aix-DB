"""
演示Schema加载的三种模式
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from framework.request_builder import CompetitionRequestBuilder


def demo():
    builder = CompetitionRequestBuilder("../target_db/competition")
    
    print("=" * 60)
    print("Case #1 的不同加载模式对比")
    print("=" * 60)
    
    # 模式1: 只加载主表
    req1 = builder.build_request(1, include_related_tables=False, include_all_tables=False)
    print(f"\n1. 只加载主表: {len(req1['schema_info']['tables'])} 个表")
    print(f"   表名: {[t['name'] for t in req1['schema_info']['tables']]}")
    
    # 模式2: 前缀匹配（默认）
    req2 = builder.build_request(1, include_related_tables=True, include_all_tables=False)
    print(f"\n2. 前缀匹配（默认）: {len(req2['schema_info']['tables'])} 个表")
    print(f"   表名: {[t['name'] for t in req2['schema_info']['tables']]}")
    
    # 模式3: 加载所有表
    req3 = builder.build_request(1, include_all_tables=True)
    print(f"\n3. 加载所有表: {len(req3['schema_info']['tables'])} 个表")
    print(f"   表名: {len(req3['schema_info']['tables'])} 个表（共20个）")
    
    print("\n" + "=" * 60)
    print("说明:")
    print("- 主表: item_callback_total_day")
    print("- 前缀 'item' 匹配: items_*, item_bmh_*, item_callback_*, item_overdue_*")
    print("- 其他表如 order_*, sub_* 等未被匹配")
    print("=" * 60)


if __name__ == "__main__":
    demo()
