# SQLite支持及提示词模板实现规划

## 一、目标数据库分析

### 1.1 数据库信息
- **类型**: SQLite
- **路径**: `/Users/liam/LLMPro/Aix-DB/target_db/competition/final.db`
- **表数量**: 22张表

### 1.2 表结构概览

| 表名 | 说明 | 核心字段 |
|------|------|----------|
| call_overview_total_day | 呼叫总体情况 | busi_time, call_cnt, connect_cnt, satisfaction_cnt |
| call_connect_total_day | 呼叫接通情况 | busi_time, hand_up_type, hand_up_cnt |
| area_items_total_day | 地区统计 | area_name, busi_time, total_num |
| accept_src_items_total_day | 受理来源统计 | accept_src_name, busi_time, total_num |
| order_type_items_total_day | 工单类型统计 | order_type_name, busi_time, total_num |
| item_bmh_total_day | 办件回复情况 | busi_time, reply_total, receive_cnt, handle_cnt |
| assess_items_total_day | 考核项目 | busi_time, dept_type, item_num, complete_num |
| sub_accept_total_day | 专题受理 | busi_time, sub_name, accept_name, accept_cnt |
| sub_top_total_day | 专题TOP | busi_time, sub_name, top_name, top_cnt |
| sub_type_total_day | 专题类型 | busi_time, sub_name, type_name, type_cnt |
| sub_area_total_day | 专题地区 | busi_time, sub_name, area, order_cnt |
| sub_warn_total_day | 专题预警 | busi_time, sub_name, red_cnt, yellow_cnt |
| order_status_total_day | 工单状态 | busi_time, order_status, order_cnt |
| sub_monitor_total_day | 专题监控 | busi_time, sub_name, name, type_name, item_num |
| sub_assess_total_day | 专题考核 | busi_time, sub_name, assess_cnt, satisfaction_*_cnt |
| items_total_day | 工单总体 | busi_time, satis_num, connect_num, item_num |
| item_callback_total_day | 回访统计 | busi_time, callback_type, callback_cnt |
| order_flow_total_day | 工单流转 | busi_date, dept_name, flow_stage, total_cnt |
| order_full_total_day | 工单全量 | busi_date, region_name, total_orders, process_orders |
| item_overdue_total_day | 逾期统计 | busi_time, type_name, due_cnt, overdue_cnt |

### 1.3 数据特点
- 所有表都有 `busi_time`/`busi_date` 字段（业务时间）
- 专题相关表有 `sub_name` 字段（专题名称）
- 统计类数据为主，适合聚合查询
- 时间范围查询是常见场景

## 二、实现规划

### 2.1 新增SQLite支持

**文件**: `algorithm-service/app/core/database.py`

```python
import sqlite3
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)

class SQLiteExecutor:
    """SQLite数据库执行器"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    async def execute(self, sql: str) -> Dict[str, Any]:
        """执行SQL查询"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute(sql)
            
            # 获取列名
            columns = [description[0] for description in cursor.description] if cursor.description else []
            
            # 获取数据
            rows = cursor.fetchall()
            data = [dict(row) for row in rows]
            
            conn.close()
            
            return {
                "success": True,
                "row_count": len(data),
                "columns": columns,
                "rows": [[row.get(col) for col in columns] for row in data],
                "execution_time_ms": 0  # 后续添加计时
            }
        except Exception as e:
            logger.error(f"SQL执行错误: {e}")
            return {
                "success": False,
                "error": str(e),
                "row_count": 0,
                "columns": [],
                "rows": []
            }
    
    def get_schema_info(self) -> Dict[str, Any]:
        """获取数据库Schema信息"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 获取所有表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = cursor.fetchall()
        
        schema_info = {"tables": []}
        
        for (table_name,) in tables:
            # 获取表结构
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            
            fields = []
            for col in columns:
                # cid, name, type, notnull, dflt_value, pk
                fields.append({
                    "name": col[1],
                    "type": col[2],
                    "is_primary": col[5] == 1,
                    "comment": ""  # SQLite无注释，后续从Excel读取
                })
            
            schema_info["tables"].append({
                "name": table_name,
                "comment": self._get_table_comment(table_name),
                "fields": fields
            })
        
        conn.close()
        return schema_info
    
    def _get_table_comment(self, table_name: str) -> str:
        """获取表注释（从注释文件或预设映射）"""
        comments = {
            "call_overview_total_day": "呼叫总体情况统计表",
            "call_connect_total_day": "呼叫接通情况统计表",
            "area_items_total_day": "地区工单统计表",
            "accept_src_items_total_day": "受理来源统计表",
            "order_type_items_total_day": "工单类型统计表",
            "item_bmh_total_day": "办件回复情况统计表",
            "assess_items_total_day": "考核项目统计表",
            "sub_accept_total_day": "专题受理统计表",
            "sub_top_total_day": "专题TOP统计表",
            "sub_type_total_day": "专题类型统计表",
            "sub_area_total_day": "专题地区统计表",
            "sub_warn_total_day": "专题预警统计表",
            "order_status_total_day": "工单状态统计表",
            "sub_monitor_total_day": "专题监控统计表",
            "sub_assess_total_day": "专题考核统计表",
            "items_total_day": "工单总体统计表",
            "item_callback_total_day": "回访统计表",
            "order_flow_total_day": "工单流转统计表",
            "order_full_total_day": "工单全量统计表",
            "item_overdue_total_day": "逾期统计表",
        }
        return comments.get(table_name, "")
```

### 2.2 创建提示词模板

**文件**: `algorithm-service/app/agent/text2sql/template/yaml/sqlite_template.yaml`

```yaml
# SQLite专用提示词模板
# 针对政务热线数据分析场景优化

sql_generation:
  system: |
    你是一个专业的SQL生成助手，专门用于分析SQLite数据库中的政务热线数据。
    
    ## 数据库类型
    SQLite 3
    
    ## 数据特点
    1. 所有表都是按天统计的日汇总表
    2. 时间字段为 TEXT 类型，格式为 'yyyy-MM-dd'
    3. 主要统计指标包括：工单量、办结量、满意度、处理时长等
    4. 专题数据以 'sub_' 开头的表存储
    
    ## SQL编写规范
    1. 使用标准SQL语法（SQLite兼容）
    2. 日期处理使用 DATE() 函数，如：DATE(busi_time) >= DATE('now', '-7 days')
    3. 字符串拼接使用 || 操作符
    4. 聚合函数：COUNT, SUM, AVG, MAX, MIN
    5. 条件判断使用 CASE WHEN ... THEN ... ELSE ... END
    
    ## 常见查询模式
    
    ### 时间范围查询
    - 最近7天: DATE(busi_time) >= DATE('now', '-7 days')
    - 本月: strftime('%Y-%m', busi_time) = strftime('%Y-%m', 'now')
    - 特定日期: busi_time = '2024-01-15'
    
    ### 专题查询
    - 专题名称字段：sub_name
    - 常用专题：'营商环境', '疫情防控', '交通拥堵' 等
    
    ### 排序和限制
    - 使用 ORDER BY 排序
    - 使用 LIMIT 限制返回条数
    
    ## 表结构信息
    {schema}
    
    ## 术语说明
    {terminologies}
    
    ## 示例
    {examples}
    
    请根据用户问题生成SQL查询语句，返回JSON格式：
    {{
      "success": true,
      "sql": "生成的SQL语句",
      "chart_type": "图表类型(table/bar/line/pie)",
      "explanation": "SQL说明"
    }}
    
    如果无法生成SQL，返回：
    {{
      "success": false,
      "message": "无法生成的原因"
    }}

  user: |
    用户问题：{question}
    
    请生成SQL查询语句。

# 图表配置生成模板
chart_generation:
  system: |
    根据SQL查询结果，生成适合的数据可视化配置。
    
    ## 支持的图表类型
    1. table - 表格（默认）
    2. bar - 柱状图（适合分类比较）
    3. line - 折线图（适合趋势展示）
    4. pie - 饼图（适合占比展示）
    
    ## 配置格式（AntV G2Plot）
    {{
      "type": "图表类型",
      "title": "图表标题",
      "xField": "X轴字段",
      "yField": "Y轴字段",
      "seriesField": "系列字段（可选）"
    }}

# 结果总结模板
summary:
  system: |
    根据SQL查询结果，生成自然语言总结。
    
    ## 总结要求
    1. 简洁明了，突出重点数据
    2. 包含关键指标和趋势
    3. 使用中文回答
    
    ## 示例格式
    "根据查询结果，最近7天的工单总量为XXX件，其中已办结XXX件，办结率为XX%。满意度方面，非常满意XXX件，满意XXX件，总体满意度为XX%。"

# 推荐问题模板
recommendations:
  system: |
    根据当前查询的表和字段，生成3-5个相关的推荐问题。
    
    ## 推荐问题类型
    1. 时间维度：趋势分析、同比环比
    2. 空间维度：地区对比、排名
    3. 类型维度：分类统计、占比
    4. 质量维度：满意度、处理时长
    
    ## 示例
    - "最近30天的工单趋势如何？"
    - "哪个地区的工单量最多？"
    - "各类工单的占比情况？"
    - "平均处理时长是多少？"
```

### 2.3 更新算法服务支持SQLite

**修改文件**: `algorithm-service/app/api/routes.py`

1. 添加SQLite执行器初始化
2. 修改SQL执行逻辑，根据db_type选择执行器
3. 添加真实SQL执行（当前为模拟）

### 2.4 创建Schema提取工具

**文件**: `algorithm-service/tools/extract_schema.py`

```python
"""
从SQLite数据库提取Schema信息
用于生成测试数据或初始化
"""

import sqlite3
import json
from pathlib import Path

def extract_schema(db_path: str, output_path: str):
    """提取数据库Schema到JSON文件"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 获取所有表
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = cursor.fetchall()
    
    schema = {"tables": []}
    
    for (table_name,) in tables:
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        
        fields = []
        for col in columns:
            fields.append({
                "name": col[1],
                "type": col[2],
                "is_primary": col[5] == 1,
                "comment": ""
            })
        
        # 获取样例数据
        cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
        sample_data = cursor.fetchall()
        
        schema["tables"].append({
            "name": table_name,
            "comment": "",
            "fields": fields,
            "sample_data": sample_data
        })
    
    conn.close()
    
    # 保存到文件
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)
    
    print(f"Schema已保存到: {output_path}")

if __name__ == "__main__":
    db_path = "/Users/liam/LLMPro/Aix-DB/target_db/competition/final.db"
    output_path = "/Users/liam/LLMPro/Aix-DB/algorithm-service/data/schema.json"
    extract_schema(db_path, output_path)
```

### 2.5 更新测试脚本

**修改文件**: `algorithm-service/tests/test_api.py`

添加SQLite专用测试数据：

```python
SQLITE_TEST_REQUEST = {
    "query": "查询最近7天的工单总量",
    "datasource_config": {
        "db_type": "sqlite",
        "host": "",
        "port": 0,
        "database": "/Users/liam/LLMPro/Aix-DB/target_db/competition/final.db",
        "username": "",
        "password": ""
    },
    "schema_info": {
        # 从final.db提取的schema
    },
    "terminologies": [
        {"word": "工单", "description": "用户提交的诉求单"},
        {"word": "办结", "description": "工单处理完成"},
        {"word": "满意度", "description": "用户对处理结果的评价"},
        {"word": "专题", "description": "特定主题的工单分类，如营商环境、疫情防控"}
    ]
}
```

## 三、实施步骤

### Step 1: 创建SQLite执行器
- 创建 `app/core/database.py`
- 实现SQL执行和Schema提取

### Step 2: 创建提示词模板
- 创建 `app/agent/text2sql/template/yaml/sqlite_template.yaml`
- 针对政务热线场景优化

### Step 3: 更新API路由
- 修改 `app/api/routes.py`
- 集成SQLite执行器
- 实现真实SQL执行

### Step 4: 创建Schema提取工具
- 创建 `tools/extract_schema.py`
- 提取final.db的schema

### Step 5: 更新测试脚本
- 添加SQLite测试数据
- 测试真实SQL执行

## 四、验证测试

```bash
# 1. 提取Schema
python algorithm-service/tools/extract_schema.py

# 2. 启动服务
cd algorithm-service
python -m app.main

# 3. 测试SQLite查询
cd algorithm-service/tests
python test_api.py sqlite "查询最近7天的工单总量"
```

请确认此规划，确认后我将开始实施SQLite支持和提示词模板的实现。