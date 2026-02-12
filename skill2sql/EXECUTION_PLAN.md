# Skill2SQL 执行方案（仅 DeepAgent + Skills 报告链路）

> 目标：把当前项目中 **DeepAgent + Skills 驱动的 REPORT_QA** 算法链路独立成可被 HTTP 调用的模块。
> 不包含 Text2SQL/NL2SQL 的传统链路。

---

## 1) 目录与骨架

**创建目录结构**
- `skill2sql/app`
- `skill2sql/app/api`
- `skill2sql/app/core`
- `skill2sql/app/schemas`
- `skill2sql/app/deepagent`
- `skill2sql/app/deepagent/tools`
- `skill2sql/app/deepagent/skills`
- `skill2sql/app/common`

**新增文件**
- `skill2sql/app/main.py`
- `skill2sql/app/api/routes.py`
- `skill2sql/app/schemas/requests.py`
- `skill2sql/app/schemas/responses.py`
- `skill2sql/app/core/config.py`
- `skill2sql/app/core/auth.py`
- `skill2sql/app/core/sse.py`
- `skill2sql/app/common/llm_factory.py`
- `skill2sql/app/common/datasource_util.py`
- `skill2sql/requirements.txt`
- `skill2sql/README.md`

---

## 2) 代码迁移与裁剪

### 2.1 DeepAgent 主体
**迁移**
- `agent/deepagent/deep_research_agent.py` → `skill2sql/app/deepagent/deep_research_agent.py`

**裁剪**
- 删除对 `DatasourceService`、`TAiModel`、`get_db_pool`、`add_user_record` 的依赖
- 删除与其它 QA 类型相关的逻辑
- 改为使用 **请求注入的数据源配置** + `llm_factory` 构造模型

### 2.2 tools 迁移
- `agent/deepagent/tools/*` → `skill2sql/app/deepagent/tools/*`

**改造点**
- `native_sql_tools.py`
  - `set_native_datasource_info` 改为接收请求传入 datasource（type/uri/config）
  - 删除对 `model.db_connection_pool`、`DatasourceTable`、`DatasourceField` 的依赖

### 2.3 skills 迁移
- `agent/deepagent/skills/*` → `skill2sql/app/deepagent/skills/*`
- `DeepAgent` 读取路径切换为新目录
- 允许请求体传 `skills` 子集过滤加载

---

## 3) LLM 工厂
新增 `skill2sql/app/common/llm_factory.py`

**职责**
- 输入：请求体 `llm` 配置
- 输出：`ChatOpenAI` 或 `ChatOllama` 客户端
- 不读取 DB 表

**字段**
- `provider`、`model`、`base_url`、`api_key`、`temperature`、`timeout`

---

## 4) 数据源工具
新增 `skill2sql/app/common/datasource_util.py`

**职责**
- 解析 `datasource` 请求配置
- SQLAlchemy 建立连接
- 执行 SQL / 查询 schema

---

## 5) HTTP 接口与 SSE

### 5.1 路由
- `POST /report/run`
- `POST /report/stop`
- `GET /health`

### 5.2 SSE 输出
- **保持原有 DeepAgent 逻辑**：
  - 推理过程/工具调用/报告正文全部走 `t02`
  - `t14`（如保留进度）
  - `t99` 结束

---

## 6) 请求契约

### 6.1 `/report/run`
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

### 6.2 `/report/stop`
```json
{ "task_id": "xxx" }
```

---

## 7) 运行方式
```
uvicorn skill2sql.app.main:app --host 0.0.0.0 --port 8090
```

---

## 8) 验收标准
1. `/report/run` 流式输出包含推理过程与工具调用（t02）
2. `sql_db_query` 等工具能执行并回传结果
3. `/report/stop` 可终止任务并输出 t99
4. 不依赖主项目数据库表即可运行

---

## 9) 备注
- Text2SQL/NL2SQL 传统链路不在范围内
- DeepAgent 输出格式不改，保持原有 Markdown 风格输出
