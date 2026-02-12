# Skill2SQL

独立运行 DeepAgent + Skills 的 Report-QA 链路，支持 SSE 推理过程输出。

## 运行

```bash
uvicorn skill2sql.app.main:app --host 0.0.0.0 --port 8090
```

## 接口

### POST /report/run

```json
{
  "query": "近三个月销售额趋势",
  "chat_id": "c1",
  "uuid": "u1",
  "datasource": {
    "type": "mysql",
    "uri": "mysql+pymysql://user:pwd@host:3306/db",
    "db_schema": "db"
  },
  "llm": {
    "provider": "openai",
    "model": "gpt-4o-mini",
    "base_url": "https://api.openai.com/v1",
    "api_key": "sk-xxx",
    "temperature": 0.7,
    "timeout": 300
  },
  "skills": ["report-generation", "schema-exploration"],
  "options": {
    "recursion_limit": 200,
    "task_timeout": 900,
    "stream_idle_timeout": 180,
    "max_messages": 100
  }
}
```

SSE 输出包含：
- `t11`: 任务 ID（未提供时服务端会生成）
- `t02`: 推理过程/工具调用/报告正文
- `t14`: 可选进度
- `t99`: 结束

### POST /report/stop

```json
{ "task_id": "u1" }
```

### GET /health

返回 `{ "status": "ok" }`

## 鉴权

可选 API Key：
- 设置环境变量 `SKILL2SQL_API_KEY`
- 请求头使用 `Authorization: Bearer <key>` 或 `X-API-Key: <key>`

## 说明

- `task_id` 默认使用 `uuid`，未提供时会回退到 `chat_id`，仍为空则自动生成。
- `datasource.uri` 优先使用；若为空则可通过 `datasource.config` 生成。
