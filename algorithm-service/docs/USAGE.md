# 算法服务使用文档

## 快速开始

### 1. 安装依赖

```bash
cd algorithm-service

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 安装向量检索依赖
pip install chromadb sentence-transformers
```

### 2. 初始化数据库

```bash
# 初始化业务库表结构（术语表、SQL示例表、Schema表）
python app/db/init_vector_tables.py
```

### 3. 配置环境变量

```bash
# 创建 .env 文件
cat > .env << EOF
# 数据库配置
DATABASE_URL=sqlite:///data/aix_db.db

# 向量存储配置
CHROMA_DB_PATH=./data/chroma_db
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# LLM配置
LLM_MODEL=gpt-4
LLM_API_KEY=your_api_key
LLM_TEMPERATURE=0.0
EOF
```

### 4. 启动服务

```bash
# 启动算法服务
python -m app.main

# 服务将在 http://localhost:8000 启动
```

## 核心功能使用

### 1. 问题改写

```python
from agent.text2sql.rewrite import rewrite_question

# 改写用户问题
original = "请帮我查一下昨天的工单量"
rewritten = rewrite_question(original)

print(f"原始: {original}")
print(f"改写: {rewritten}")
# 输出: 查询2024-01-21的工单量
```

**支持的改写类型**:
- 时间标准化: "昨天" → "2024-01-21"
- 去除填充词: "请帮我查" → "查询"
- 标点标准化

### 2. 向量精排

```python
from agent.text2sql.ranking import rank_candidates

# 准备候选内容
candidates = {
    "terminologies": [
        {"term": "工单量", "description": "工单的数量"},
        {"term": "回访量", "description": "回访的次数"},
        {"term": "满意度", "description": "客户满意度评分"},
    ],
    "sql_examples": [
        {"question": "查询工单量", "sql": "SELECT COUNT(*) FROM tickets"},
        {"question": "查询昨天的数据", "sql": "SELECT * FROM tickets WHERE created_at >= '2024-01-21'"},
    ]
}

# 向量精排
result = rank_candidates(
    question="查询昨天的工单量",
    terminologies=candidates["terminologies"],
    sql_examples=candidates["sql_examples"],
    top_k_terms=3,
    top_k_examples=2
)

# 使用精排结果
for item in result["terminologies"]:
    print(f"术语: {item.item['term']}, 相似度: {item.score:.2f}")

for item in result["sql_examples"]:
    print(f"示例: {item.item['question']}, 相似度: {item.score:.2f}")
```

### 3. SQL验证

```python
from agent.text2sql.validation import validate_sql

# 验证SQL
result = validate_sql(
    question="查询昨天的工单量",
    sql="SELECT COUNT(*) FROM tickets WHERE created_at >= '2024-01-21'",
    schema={
        "tables": [
            {"name": "tickets", "columns": ["id", "created_at", "status"]}
        ]
    },
    db_type="mysql"
)

print(f"验证通过: {result.valid}")
print(f"综合得分: {result.score:.2f}")
print(f"通过的检查: {result.passed_checks}")
print(f"反馈: {result.feedback}")
```

**验证维度**:
- `syntax`: 语法检查
- `semantic`: 语义匹配
- `schema`: Schema检查

### 4. 迭代生成

```python
from agent.text2sql.generation import generate_with_validation
from common.llm_util import get_llm

# 定义生成函数
def generate_sql(question):
    llm = get_llm(temperature=0)
    # 构建Prompt并调用LLM
    prompt = f"生成SQL: {question}"
    response = llm.invoke(prompt)
    return response.content

# 带验证的生成
result = generate_with_validation(
    question="查询昨天的工单量",
    generate_func=generate_sql,
    schema={...},
    db_type="mysql",
    max_retries=3
)

print(f"生成的SQL: {result.sql}")
print(f"是否成功: {result.success}")
print(f"尝试次数: {result.attempts}")
print(f"最终验证得分: {result.final_validation.score:.2f}")
```

### 5. 完整NL2SQL流程

```python
from agent.text2sql.rewrite import rewrite_question
from agent.text2sql.ranking import rank_candidates
from agent.text2sql.validation import validate_sql
from agent.text2sql.sql.generator import sql_generate
from agent.text2sql.state.agent_state import AgentState

# 1. 准备状态
state: AgentState = {
    "user_query": "请帮我查一下昨天的工单量",
    "db_info": {
        "tickets": {
            "columns": {
                "id": {"type": "INT", "comment": "工单ID"},
                "created_at": {"type": "DATETIME", "comment": "创建时间"},
                "status": {"type": "VARCHAR", "comment": "状态"}
            },
            "table_comment": "工单表"
        }
    },
    "datasource_id": 1,
    "candidates": {
        "terminologies": [
            {"term": "工单量", "description": "工单的数量"}
        ],
        "sql_examples": [
            {"question": "查询工单量", "sql": "SELECT COUNT(*) FROM tickets"}
        ]
    }
}

# 2. 执行生成流程
result_state = sql_generate(state)

# 3. 获取结果
generated_sql = result_state["generated_sql"]
validation_info = result_state.get("sql_validation", {})

print(f"生成的SQL: {generated_sql}")
print(f"验证得分: {validation_info.get('score', 0):.2f}")
print(f"验证反馈: {validation_info.get('feedback', '')}")
```

## 聊天服务使用

### 1. 创建会话

```python
from chat_service.service import ChatService

# 初始化服务
chat_service = ChatService()

# 创建新会话
session = chat_service.create_session(title="工单分析")
print(f"会话ID: {session.id}")
```

### 2. 发送消息

```python
# 流式发送消息
async for event in chat_service.process_message(
    session_id=session.id,
    message="查询昨天的工单量",
    datasource_id=1
):
    event_type = event.get("event_type")
    
    if event_type == "sql_generated":
        print(f"SQL: {event['data']['sql']}")
    elif event_type == "summary":
        print(f"总结: {event['data']['text']}")
    elif event_type == "error":
        print(f"错误: {event['message']}")
```

### 3. 管理术语

```python
# 添加术语
terminology = chat_service.add_terminology(
    term="工单量",
    description="工单的数量，按状态统计",
    category="metrics"
)

# 获取术语列表
terms = chat_service.get_terminologies(category="metrics")
for term in terms:
    print(f"{term['term']}: {term['description']}")
```

### 4. 管理SQL示例

```python
# 添加SQL示例
example = chat_service.add_sql_example(
    question="查询昨天的工单量",
    sql="SELECT COUNT(*) FROM tickets WHERE created_at >= '2024-01-21'",
    description="按日期统计工单数量",
    datasource_id=1
)

# 获取SQL示例
examples = chat_service.get_sql_examples(datasource_id=1)
for ex in examples:
    print(f"Q: {ex['question']}")
    print(f"SQL: {ex['sql']}")
```

## 向量存储管理

### 1. 同步数据到向量库

```python
from rag.sync import add_terminology, add_sql_example, sync_datasource_schema

# 添加术语（自动同步到向量库）
term = add_terminology(
    term="回访量",
    definition="客服回访的次数"
)

# 添加SQL示例（自动同步到向量库）
example = add_sql_example(
    question="查询昨天的工单量",
    sql="SELECT COUNT(*) FROM tickets"
)

# 同步数据源Schema（首次连接时自动调用）
sync_datasource_schema(
    datasource_id=1,
    schema_info={...}
)
```

### 2. 向量检索

```python
from rag.vector_store import ChromaVectorStore

# 初始化向量存储
store = ChromaVectorStore("terminologies")

# 添加文档
doc_id = store.add_document(
    content="工单量: 工单的数量",
    metadata={"term": "工单量", "category": "metrics"}
)

# 相似度搜索
results = store.similarity_search(
    query="查询工单数量",
    top_k=5
)

for doc, score in results:
    print(f"内容: {doc.page_content}, 相似度: {score:.2f}")
```

## API接口

### 1. 生成SQL

```bash
curl -X POST http://localhost:8000/api/text2sql \
  -H "Content-Type: application/json" \
  -d '{
    "question": "查询昨天的工单量",
    "datasource_id": 1,
    "schema_info": {...}
  }'
```

**响应**:
```json
{
  "sql": "SELECT COUNT(*) FROM tickets WHERE created_at >= '2024-01-21'",
  "validation": {
    "valid": true,
    "score": 0.85,
    "feedback": "SQL验证通过"
  }
}
```

### 2. 流式聊天

```bash
curl -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": 1,
    "message": "查询昨天的工单量",
    "datasource_id": 1
  }'
```

**响应** (SSE流):
```
event: sql_generated
data: {"sql": "SELECT COUNT(*) FROM tickets..."}

event: summary
data: {"text": "昨天共有100个工单"}
```

### 3. 管理术语

```bash
# 添加术语
curl -X POST http://localhost:8000/api/terminologies \
  -H "Content-Type: application/json" \
  -d '{
    "term": "工单量",
    "description": "工单的数量"
  }'

# 获取术语列表
curl http://localhost:8000/api/terminologies
```

## 配置说明

### 问题改写配置

```python
# app/agent/text2sql/rewrite/question_rewriter.py

# 自定义填充词
FILLER_WORDS = [
    r'请帮我', r'请', r'帮我',
    r'能不能', r'可以',
    # 添加更多...
]
```

### 向量精排配置

```python
# app/agent/text2sql/ranking/vector_ranker.py

# 调整Top K数量
rank_terminologies(top_k=5)   # 默认5个术语
rank_sql_examples(top_k=3)    # 默认3个示例
```

### SQL验证配置

```python
# app/agent/text2sql/validation/sql_validator.py

# 调整验证阈值
validate_sql(threshold=0.6)   # 语义匹配阈值

# 调整得分权重
_syntax_weight = 0.4          # 语法权重
_semantic_weight = 0.4        # 语义权重
_schema_weight = 0.2          # Schema权重
```

### 迭代生成配置

```python
# app/agent/text2sql/generation/iterative_generator.py

# 调整重试次数
generate_with_validation(max_retries=3)

# 调整成功阈值
if validation.score >= 0.7:   # 默认0.7分算成功
    return result
```

## 故障排查

### 1. 向量检索失败

**症状**: 日志显示"向量检索失败"

**解决**:
```bash
# 检查ChromaDB目录
ls -la data/chroma_db

# 重新初始化向量库
rm -rf data/chroma_db
python app/db/init_vector_tables.py
```

### 2. 嵌入模型加载失败

**症状**: 日志显示"嵌入模型加载失败"

**解决**:
```bash
# 手动下载模型
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

# 或配置本地模型路径
export EMBEDDING_MODEL=/path/to/local/model
```

### 3. SQL验证失败

**症状**: 生成的SQL验证不通过

**解决**:
- 检查Schema信息是否正确
- 调整验证阈值
- 查看验证反馈信息，针对性优化Prompt

### 4. 迭代生成超时

**症状**: SQL生成时间过长

**解决**:
```python
# 减少重试次数
generate_with_validation(max_retries=2)

# 简化验证逻辑
validate_sql(skip_semantic=True)  # 跳过语义验证
```

## 最佳实践

### 1. 术语管理

- 保持术语简洁明了
- 为每个术语添加详细描述
- 按类别组织术语
- 定期更新术语库

### 2. SQL示例管理

- 提供高质量的SQL示例
- 覆盖常见查询场景
- 包含复杂查询（JOIN、子查询等）
- 定期根据用户反馈更新

### 3. Prompt优化

- 使用改写后的问题进行检索
- 结合向量精排和传统检索
- 在Prompt中明确指定数据库类型
- 提供清晰的示例和规则

### 4. 性能优化

- 启用模板缓存
- 使用连接池管理数据库连接
- 对频繁查询的结果进行缓存
- 监控向量检索性能

---

**更多文档**:
- [架构设计](ARCHITECTURE.md)
- [API文档](API.md)
- [开发指南](DEVELOPMENT.md)
