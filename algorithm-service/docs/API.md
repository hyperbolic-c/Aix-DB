# 算法服务 API 文档

## 基础信息

- **基础URL**: `http://localhost:8000`
- **API版本**: `v1`
- **内容类型**: `application/json`

---

## 1. Text2SQL API

### 1.1 生成SQL

**请求**:
```http
POST /api/text2sql
Content-Type: application/json

{
    "question": "查询昨天的工单量",
    "datasource_id": 1,
    "schema_info": {
        "tables": [
            {
                "name": "tickets",
                "columns": [
                    {"name": "id", "type": "INT"},
                    {"name": "created_at", "type": "DATETIME"},
                    {"name": "status", "type": "VARCHAR"}
                ]
            }
        ]
    },
    "enable_rewrite": true,
    "enable_validation": true
}
```

**响应**:
```json
{
    "success": true,
    "data": {
        "sql": "SELECT COUNT(*) FROM tickets WHERE created_at >= '2024-01-21'",
        "rewritten_question": "查询2024-01-21的工单量",
        "validation": {
            "valid": true,
            "score": 0.85,
            "passed_checks": ["syntax", "semantic"],
            "feedback": "SQL验证通过"
        },
        "used_tables": ["tickets"],
        "execution_time_ms": 1234
    }
}
```

**错误响应**:
```json
{
    "success": false,
    "error": {
        "code": "GENERATION_FAILED",
        "message": "SQL生成失败",
        "details": "无法识别表结构"
    }
}
```

### 1.2 验证SQL

**请求**:
```http
POST /api/text2sql/validate
Content-Type: application/json

{
    "question": "查询昨天的工单量",
    "sql": "SELECT COUNT(*) FROM tickets WHERE created_at >= '2024-01-21'",
    "schema_info": {...},
    "db_type": "mysql"
}
```

**响应**:
```json
{
    "success": true,
    "data": {
        "valid": true,
        "score": 0.85,
        "passed_checks": ["syntax", "semantic", "schema"],
        "failed_checks": [],
        "warnings": [],
        "feedback": "SQL验证通过",
        "details": {
            "syntax": {
                "valid": true,
                "details": {...}
            },
            "semantic": {
                "score": 0.85,
                "matched": true,
                "analysis": "语义匹配良好"
            },
            "schema": {
                "valid": true,
                "details": {...}
            }
        }
    }
}
```

### 1.3 改写问题

**请求**:
```http
POST /api/text2sql/rewrite
Content-Type: application/json

{
    "question": "请帮我查一下昨天的工单量"
}
```

**响应**:
```json
{
    "success": true,
    "data": {
        "original": "请帮我查一下昨天的工单量",
        "rewritten": "查询2024-01-21的工单量",
        "changes": [
            "去除填充词: '请帮我查一下' -> '查询'",
            "时间标准化: '昨天' -> '2024-01-21'"
        ]
    }
}
```

---

## 2. 聊天服务 API

### 2.1 创建会话

**请求**:
```http
POST /api/chat/sessions
Content-Type: application/json

{
    "title": "工单分析"
}
```

**响应**:
```json
{
    "success": true,
    "data": {
        "id": 1,
        "title": "工单分析",
        "created_at": "2024-01-21T10:00:00Z",
        "updated_at": "2024-01-21T10:00:00Z"
    }
}
```

### 2.2 获取会话列表

**请求**:
```http
GET /api/chat/sessions?page=1&page_size=20
```

**响应**:
```json
{
    "success": true,
    "data": {
        "items": [
            {
                "id": 1,
                "title": "工单分析",
                "created_at": "2024-01-21T10:00:00Z",
                "updated_at": "2024-01-21T10:00:00Z"
            }
        ],
        "total": 1,
        "page": 1,
        "page_size": 20
    }
}
```

### 2.3 发送消息（流式）

**请求**:
```http
POST /api/chat/sessions/{session_id}/messages
Content-Type: application/json

{
    "message": "查询昨天的工单量",
    "datasource_id": 1
}
```

**响应** (SSE流):
```
event: thinking
data: {"message": "正在分析问题..."}

event: sql_generating
data: {"message": "正在生成SQL..."}

event: sql_generated
data: {
    "sql": "SELECT COUNT(*) FROM tickets WHERE created_at >= '2024-01-21'",
    "validation": {
        "valid": true,
        "score": 0.85
    }
}

event: executing
data: {"message": "正在执行SQL..."}

event: summary
data: {
    "text": "昨天共有100个工单",
    "data": {
        "columns": ["count"],
        "rows": [[100]]
    }
}

event: done
data: {"message": "处理完成"}
```

### 2.4 获取消息历史

**请求**:
```http
GET /api/chat/sessions/{session_id}/messages
```

**响应**:
```json
{
    "success": true,
    "data": {
        "items": [
            {
                "id": 1,
                "role": "user",
                "content": "查询昨天的工单量",
                "created_at": "2024-01-21T10:00:00Z"
            },
            {
                "id": 2,
                "role": "assistant",
                "content": "昨天共有100个工单",
                "sql": "SELECT COUNT(*) FROM tickets...",
                "created_at": "2024-01-21T10:00:01Z"
            }
        ]
    }
}
```

---

## 3. 术语管理 API

### 3.1 添加术语

**请求**:
```http
POST /api/terminologies
Content-Type: application/json

{
    "term": "工单量",
    "description": "工单的数量，按状态统计",
    "category": "metrics",
    "synonyms": ["工单数", "工单总量"]
}
```

**响应**:
```json
{
    "success": true,
    "data": {
        "id": 1,
        "term": "工单量",
        "description": "工单的数量，按状态统计",
        "category": "metrics",
        "synonyms": ["工单数", "工单总量"],
        "created_at": "2024-01-21T10:00:00Z",
        "synced_to_vector": true
    }
}
```

### 3.2 获取术语列表

**请求**:
```http
GET /api/terminologies?category=metrics&page=1&page_size=20
```

**响应**:
```json
{
    "success": true,
    "data": {
        "items": [
            {
                "id": 1,
                "term": "工单量",
                "description": "工单的数量，按状态统计",
                "category": "metrics",
                "synonyms": ["工单数"]
            }
        ],
        "total": 1,
        "page": 1,
        "page_size": 20
    }
}
```

### 3.3 更新术语

**请求**:
```http
PUT /api/terminologies/{id}
Content-Type: application/json

{
    "description": "工单的数量（更新后的描述）",
    "category": "metrics"
}
```

**响应**:
```json
{
    "success": true,
    "data": {
        "id": 1,
        "term": "工单量",
        "description": "工单的数量（更新后的描述）",
        "category": "metrics",
        "updated_at": "2024-01-21T10:00:00Z"
    }
}
```

### 3.4 删除术语

**请求**:
```http
DELETE /api/terminologies/{id}
```

**响应**:
```json
{
    "success": true,
    "message": "术语已删除"
}
```

### 3.5 搜索术语

**请求**:
```http
GET /api/terminologies/search?q=工单&top_k=5
```

**响应**:
```json
{
    "success": true,
    "data": {
        "items": [
            {
                "id": 1,
                "term": "工单量",
                "description": "工单的数量",
                "score": 0.95
            },
            {
                "id": 2,
                "term": "工单",
                "description": "工作单",
                "score": 0.88
            }
        ]
    }
}
```

---

## 4. SQL示例管理 API

### 4.1 添加SQL示例

**请求**:
```http
POST /api/sql-examples
Content-Type: application/json

{
    "question": "查询昨天的工单量",
    "sql": "SELECT COUNT(*) FROM tickets WHERE created_at >= '2024-01-21'",
    "description": "按日期统计工单数量",
    "datasource_id": 1,
    "is_public": true
}
```

**响应**:
```json
{
    "success": true,
    "data": {
        "id": 1,
        "question": "查询昨天的工单量",
        "sql": "SELECT COUNT(*) FROM tickets WHERE created_at >= '2024-01-21'",
        "description": "按日期统计工单数量",
        "datasource_id": 1,
        "is_public": true,
        "created_at": "2024-01-21T10:00:00Z",
        "synced_to_vector": true
    }
}
```

### 4.2 获取SQL示例列表

**请求**:
```http
GET /api/sql-examples?datasource_id=1&page=1&page_size=20
```

**响应**:
```json
{
    "success": true,
    "data": {
        "items": [
            {
                "id": 1,
                "question": "查询昨天的工单量",
                "sql": "SELECT COUNT(*) FROM tickets...",
                "description": "按日期统计工单数量",
                "datasource_id": 1
            }
        ],
        "total": 1,
        "page": 1,
        "page_size": 20
    }
}
```

### 4.3 搜索SQL示例

**请求**:
```http
GET /api/sql-examples/search?q=工单量&datasource_id=1&top_k=5
```

**响应**:
```json
{
    "success": true,
    "data": {
        "items": [
            {
                "id": 1,
                "question": "查询昨天的工单量",
                "sql": "SELECT COUNT(*) FROM tickets...",
                "score": 0.92
            }
        ]
    }
}
```

---

## 5. 向量检索 API

### 5.1 相似度搜索

**请求**:
```http
POST /api/vector/search
Content-Type: application/json

{
    "query": "查询工单数量",
    "collection": "terminologies",
    "top_k": 5,
    "filter": {
        "category": "metrics"
    }
}
```

**响应**:
```json
{
    "success": true,
    "data": {
        "items": [
            {
                "content": "工单量: 工单的数量",
                "metadata": {
                    "term": "工单量",
                    "category": "metrics"
                },
                "score": 0.95
            }
        ]
    }
}
```

### 5.2 添加文档到向量库

**请求**:
```http
POST /api/vector/documents
Content-Type: application/json

{
    "collection": "terminologies",
    "content": "工单量: 工单的数量",
    "metadata": {
        "term": "工单量",
        "category": "metrics"
    }
}
```

**响应**:
```json
{
    "success": true,
    "data": {
        "doc_id": "uuid-string",
        "collection": "terminologies"
    }
}
```

---

## 6. 数据源管理 API

### 6.1 连接数据源

**请求**:
```http
POST /api/datasources/{id}/connect
Content-Type: application/json

{
    "sync_schema": true
}
```

**响应**:
```json
{
    "success": true,
    "data": {
        "connected": true,
        "schema_synced": true,
        "tables_count": 10,
        "sync_time_ms": 1234
    }
}
```

### 6.2 获取数据源Schema

**请求**:
```http
GET /api/datasources/{id}/schema
```

**响应**:
```json
{
    "success": true,
    "data": {
        "tables": [
            {
                "name": "tickets",
                "comment": "工单表",
                "columns": [
                    {
                        "name": "id",
                        "type": "INT",
                        "comment": "工单ID"
                    },
                    {
                        "name": "created_at",
                        "type": "DATETIME",
                        "comment": "创建时间"
                    }
                ]
            }
        ]
    }
}
```

### 6.3 同步Schema到向量库

**请求**:
```http
POST /api/datasources/{id}/sync-schema
```

**响应**:
```json
{
    "success": true,
    "data": {
        "tables_synced": 10,
        "columns_synced": 50,
        "sync_time_ms": 2345
    }
}
```

---

## 7. 系统状态 API

### 7.1 健康检查

**请求**:
```http
GET /api/health
```

**响应**:
```json
{
    "success": true,
    "data": {
        "status": "healthy",
        "version": "1.2.0",
        "uptime_seconds": 3600,
        "components": {
            "database": "connected",
            "vector_store": "connected",
            "llm": "available"
        }
    }
}
```

### 7.2 获取配置信息

**请求**:
```http
GET /api/config
```

**响应**:
```json
{
    "success": true,
    "data": {
        "version": "1.2.0",
        "features": {
            "rewrite_enabled": true,
            "validation_enabled": true,
            "vector_ranking_enabled": true
        },
        "limits": {
            "max_sql_length": 10000,
            "max_query_time_ms": 30000,
            "max_retries": 3
        }
    }
}
```

---

## 错误码

| 错误码 | 描述 | HTTP状态码 |
|--------|------|-----------|
| `INVALID_REQUEST` | 请求参数错误 | 400 |
| `UNAUTHORIZED` | 未授权 | 401 |
| `FORBIDDEN` | 禁止访问 | 403 |
| `NOT_FOUND` | 资源不存在 | 404 |
| `GENERATION_FAILED` | SQL生成失败 | 500 |
| `VALIDATION_FAILED` | SQL验证失败 | 400 |
| `VECTOR_STORE_ERROR` | 向量存储错误 | 500 |
| `LLM_ERROR` | LLM调用错误 | 500 |
| `DATABASE_ERROR` | 数据库错误 | 500 |
| `TIMEOUT` | 请求超时 | 504 |

---

## 认证

### API Key认证

**请求头**:
```http
Authorization: Bearer {api_key}
```

### JWT认证

**请求头**:
```http
Authorization: Bearer {jwt_token}
```

---

## 分页参数

所有列表接口支持以下分页参数：

| 参数 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `page` | int | 1 | 页码 |
| `page_size` | int | 20 | 每页数量（最大100） |

**分页响应**:
```json
{
    "items": [...],
    "total": 100,
    "page": 1,
    "page_size": 20,
    "total_pages": 5
}
```

---

**更多文档**:
- [架构设计](ARCHITECTURE.md)
- [使用指南](USAGE.md)
- [模块文档](MODULES.md)
