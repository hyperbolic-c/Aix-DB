# Aix-DB 算法服务

Text2SQL算法服务，提供自然语言转SQL分析能力。

## 架构说明

本服务是Aix-DB项目的算法端独立化实现：
- **职责**: 接收后端准备好的数据，执行Text2SQL分析流程
- **数据流**: 后端准备所有数据 → HTTP调用算法服务 → 流式返回结果
- **数据库访问**: 仅连接目标数据库执行SQL，不访问业务数据库

## 目录结构

```
algorithm-service/
├── app/
│   ├── main.py              # FastAPI入口
│   ├── api/
│   │   └── routes.py        # HTTP API路由(流式SSE)
│   ├── schemas/
│   │   └── requests.py      # Pydantic请求/响应模型
│   └── agent/               # 算法核心(待迁移)
├── tests/
│   ├── stream_processor.py  # 流式响应处理模块
│   └── test_api.py          # API测试脚本
└── requirements.txt
```

## 安装依赖

```bash
cd algorithm-service
pip install -r requirements.txt
```

## 启动服务

```bash
# 开发模式(热重载)
python -m app.main

# 或使用uvicorn
uvicorn app.main:app --reload --port 8001

# 生产模式
uvicorn app.main:app --host 0.0.0.0 --port 8001 --workers 4
```

服务启动后访问:
- API文档: http://localhost:8001/docs
- 健康检查: http://localhost:8001/api/v1/health

## API接口

### 1. 健康检查

```bash
GET /api/v1/health
```

响应:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00"
}
```

### 2. Text2SQL分析(流式)

```bash
POST /api/v1/analyze
Content-Type: application/json
```

请求体:
```json
{
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
          {"name": "id", "type": "bigint", "comment": "订单ID", "is_primary": true},
          {"name": "order_date", "type": "datetime", "comment": "订单日期"}
        ]
      }
    ]
  },
  "terminologies": [
    {"word": "订单量", "description": "订单的数量，使用COUNT(*)统计"}
  ],
  "training_examples": [
    {
      "question": "查询昨天的销售额",
      "sql": "SELECT SUM(amount) FROM orders WHERE DATE(order_date) = DATE_SUB(CURDATE(), INTERVAL 1 DAY)"
    }
  ],
  "permission_rules": {
    "row_filters": [],
    "column_permissions": {}
  }
}
```

流式响应(SSE格式):
```
data: {"event_type": "step_start", "step_name": "schema_inspector", ...}
data: {"event_type": "sql_generated", "data": {"sql": "SELECT ..."}, ...}
data: {"event_type": "sql_executed", "data": {"success": true, ...}, ...}
data: {"event_type": "summary", "data": {"text": "..."}, ...}
data: {"event_type": "complete", ...}
```

## 测试

### 使用测试脚本

```bash
cd algorithm-service/tests

# 运行完整测试
python test_api.py

# 仅测试健康检查
python test_api.py health

# 使用自定义问题测试
python test_api.py custom "查询订单总额"

# 指定服务地址
ALGO_SERVICE_URL=http://localhost:8001 python test_api.py
```

### 使用curl

```bash
# 健康检查
curl http://localhost:8001/api/v1/health

# Text2SQL分析
curl -X POST http://localhost:8001/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "query": "查询订单量",
    "datasource_config": {
      "db_type": "mysql",
      "host": "localhost",
      "port": 3306,
      "database": "test_db",
      "username": "root",
      "password": "password"
    },
    "schema_info": {
      "tables": [{
        "name": "orders",
        "comment": "订单表",
        "fields": [
          {"name": "id", "type": "bigint", "comment": "订单ID", "is_primary": true}
        ]
      }]
    }
  }'
```

## 流式响应处理

测试脚本中的`stream_processor.py`模块提供了完整的流式响应处理能力:

```python
from stream_processor import StreamProcessor
import httpx

async def test():
    processor = StreamProcessor(verbose=True, use_colors=True)
    
    async with httpx.AsyncClient() as client:
        async with client.stream("POST", url, json=data) as response:
            result = await processor.process(response.aiter_lines())
    
    # 打印最终报告
    processor.print_final_report()
    
    # 获取完整结果
    print(result.sql)
    print(result.summary)
    print(result.recommendations)
```

## 数据请求体说明

算法服务需要的完整数据请求体包含:

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| query | string | ✓ | 用户问题 |
| datasource_config | object | ✓ | 数据源连接配置 |
| schema_info | object | ✓ | 表结构信息 |
| terminologies | array | ✗ | 术语列表(RAG增强) |
| training_examples | array | ✗ | 训练示例(Few-shot) |
| permission_rules | object | ✗ | 权限规则 |
| chat_history | array | ✗ | 对话历史 |
| user_id | integer | ✗ | 用户ID(日志用) |
| datasource_id | integer | ✗ | 数据源ID(日志用) |

## 开发计划

1. **Phase 1** (当前): 基础HTTP服务 + 模拟算法流程 + 流式响应处理
2. **Phase 2**: 迁移真实算法代码(LangGraph工作流)
3. **Phase 3**: 实现真实SQL执行(连接目标数据库)
4. **Phase 4**: 集成提示词模板(本地YAML文件)

## 注意事项

- 当前实现为模拟版本，用于测试流式响应架构
- 真实的SQL生成和执行将在后续版本实现
- 提示词模板将由算法端从本地文件读取
- 算法服务不访问业务数据库，仅执行目标数据库SQL
