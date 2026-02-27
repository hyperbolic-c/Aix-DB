# Text2SQL Service

独立 Text2SQL 算法服务 - 完整信息传入方案

## 概述

Text2SQL Service 是一个独立的算法服务，将原 Aix-DB 项目中的 Text2SQL 算法剥离出来，形成独立部署的服务。

**核心特点：**
- **无数据库连接** - 所有数据通过 API 传入，服务纯算法逻辑
- **完整信息传入** - 支持传入 Schema、表关系、术语、训练示例、多轮对话等完整上下文
- **独立部署** - 可独立扩展、升级，与主应用解耦

## 目录结构

```
text2sql-service/
├── app/                          # 算法服务
│   ├── main.py                   # FastAPI 入口
│   ├── api/
│   │   └── routes.py             # API 路由
│   ├── schemas/
│   │   └── requests.py           # 请求/响应模型
│   ├── generator/
│   │   ├── retriever.py          # BM25 Schema 检索
│   │   ├── prompt_builder.py     # 提示词构建
│   │   └── sql_generator.py      # SQL 生成器
│   ├── template/                 # 模板文件
│   │   ├── yaml/
│   │   │   ├── template.yaml     # 基础模板
│   │   │   └── sql_examples/     # SQL 示例
│   │   ├── template_loader.py    # 模板加载器
│   │   └── schema_formatter.py   # Schema 格式化
│   └── core/
│       └── config.py             # 服务配置
├── client/                       # 主应用客户端（与算法服务同目录）
│   ├── __init__.py
│   └── text2sql_client.py        # 主应用调用客户端
├── requirements.txt
├── Dockerfile
└── README.md
```

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 启动服务

```bash
# 开发模式
uvicorn app.main:app --reload --port 8080

# 生产模式
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

### Docker 部署

```bash
# 构建镜像
docker build -t text2sql-service .

# 运行容器
docker run -p 8080:8080 text2sql-service
```

## API 接口

### 生成 SQL

```http
POST /api/v1/sql/generate
```

**请求体：**

```json
{
  "query": "查询最近7天各状态的订单数量",
  "tables": [
    {
      "name": "orders",
      "comment": "订单表",
      "columns": [
        {"name": "id", "type": "bigint", "comment": "订单ID", "is_primary": true},
        {"name": "status", "type": "varchar", "comment": "订单状态"},
        {"name": "created_at", "type": "datetime", "comment": "创建时间"}
      ]
    }
  ],
  "db_type": "mysql",
  "db_name": "ecommerce",
  "llm": {
    "provider": "openai",
    "model": "gpt-4o-mini",
    "api_key": "sk-xxx",
    "temperature": 0.7
  },
  "chat_history": [
    {"role": "user", "content": "查询最近7天的订单"},
    {"role": "assistant", "content": "已为您查询", "sql": "SELECT * FROM orders WHERE created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY) LIMIT 40"}
  ],
  "terminologies": "订单状态包括：pending(待处理)、paid(已支付)...",
  "enable_query_limit": true
}
```

**响应：**

```json
{
  "success": true,
  "sql": "SELECT status, COUNT(*) as count FROM orders WHERE created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY) GROUP BY status LIMIT 40",
  "chart_type": "column",
  "used_tables": ["orders"],
  "retrieved_tables": ["orders"],
  "tokens": ["查询", "最近", "7天", "状态", "订单", "数量"]
}
```

### 健康检查

```http
GET /api/v1/health
```

## 主应用客户端使用

```python
from text2sql-service.client import Text2SQLServiceClient

# 创建客户端
client = Text2SQLServiceClient(base_url="http://localhost:8080")

# 调用生成 SQL
result = await client.generate_sql(
    query="查询最近7天的订单",
    tables=[...],  # 全量表结构
    db_type="mysql",
    db_name="ecommerce",
    llm_config=LLMConfig(
        provider="openai",
        model="gpt-4o-mini",
        api_key="sk-xxx"
    ),
    chat_history=[...],  # 多轮对话历史
    terminologies="...",  # 术语
    training_examples="..."  # 训练示例
)

print(result["sql"])
```

## 完整信息传入

服务接收原实现中 SQL 生成所需的全部信息：

| 信息类型 | 说明 |
|---------|------|
| Schema | 全量表结构，通过 `tables` 传入 |
| 数据库类型 | `db_type`: mysql/postgresql/oracle/... |
| 数据库名 | `db_name`: 数据库名/Schema名 |
| 表关系 | `table_relations`: 用于 JOIN 生成 |
| LLM 配置 | `llm`: 模型、API Key、温度等 |
| 多轮对话 | `chat_history`: 聊天记录 |
| 术语 | `terminologies`: 业务术语定义 |
| 训练示例 | `training_examples`: SQL 示例 |
| 错误信息 | `error_message`: 用于纠错重试 |

## 与原实现的对比

### 原实现

```
主应用 → AgentState → sql_generate() 
  → 查询数据库获取 Schema
  → 查询表关系
  → RAG 检索术语/示例
  → 构建提示词
  → 调用 LLM
```

### 新实现

```
主应用 → 查询所有信息 → text2sql_client 
  → HTTP 请求 → Text2SQL Service
    → BM25 Schema 检索
    → 构建提示词
    → 调用 LLM
```

**优势：**
- 算法服务零数据库连接，纯算法逻辑
- 主应用完全控制传入信息
- 独立部署，易于扩展
- 任何语言的主应用均可调用

## License

MIT
