# 算法服务架构文档

## 概述

算法服务是Aix-DB项目的核心智能层，负责将自然语言问题转换为可执行的SQL查询。本文档描述了算法服务的整体架构、核心模块和关键流程。

## 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         算法服务 (algorithm-service)              │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   API层     │  │  聊天服务    │  │      向量存储            │  │
│  │  (main.py)  │  │(chat_service)│  │   (vector_store)        │  │
│  └──────┬──────┘  └──────┬──────┘  └─────────────────────────┘  │
│         │                │                                       │
│         └────────────────┼───────────────────────────────────────┘
│                          │
│  ┌───────────────────────┴─────────────────────────────────────┐  │
│  │                    Agent工作流 (agent/text2sql)               │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────────┐ │  │
│  │  │问题改写  │ │表检索    │ │SQL生成   │ │SQL执行与总结    │ │  │
│  │  │(rewrite) │ │(retrieval)│ │(generate)│ │(execute/summary)│ │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └─────────────────┘ │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                          │
│  ┌───────────────────────┴─────────────────────────────────────┐  │
│  │                    支持模块                                   │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────────┐ │  │
│  │  │向量精排  │ │SQL验证   │ │模板系统  │ │数据服务        │ │  │
│  │  │(ranking) │ │(validate)│ │(template)│ │(db_service)     │ │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └─────────────────┘ │  │
│  └─────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## 核心模块

### 1. Agent工作流 (agent/text2sql)

#### 1.1 问题改写 (rewrite)

**文件位置**: `app/agent/text2sql/rewrite/`

**功能**: 对用户输入的问题进行轻量级规范化改写，提高SQL生成质量。

**组件**:
- `QuestionRewriter`: 问题改写器，去除填充词、标准化时间
- `TimeNormalizer`: 时间标准化，将相对时间转换为绝对日期

**改写流程**:
```
用户问题: "请帮我查一下昨天的工单量"
    ↓
去除填充词: "查昨天工单量"
    ↓
时间标准化: "查2024-01-21工单量"
    ↓
输出: "查询2024-01-21的工单量"
```

**使用示例**:
```python
from agent.text2sql.rewrite import rewrite_question

rewritten = rewrite_question("请帮我查一下昨天的工单量")
# 输出: "查询2024-01-21的工单量"
```

#### 1.2 向量精排 (ranking)

**文件位置**: `app/agent/text2sql/ranking/`

**功能**: 对后端发送的候选术语和SQL示例进行向量相似度精排。

**组件**:
- `VectorRanker`: 向量精排器，计算查询与候选内容的相似度
- `RankedItem`: 排序结果项

**精排流程**:
```
用户问题 + 候选术语/SQL示例
    ↓
生成查询向量
    ↓
计算余弦相似度
    ↓
按相似度排序
    ↓
返回Top K结果
```

**使用示例**:
```python
from agent.text2sql.ranking import rank_candidates

result = rank_candidates(
    question="查询昨天的工单量",
    terminologies=[{"term": "工单量", "description": "..."}, ...],
    sql_examples=[{"question": "...", "sql": "..."}, ...],
    top_k_terms=5,
    top_k_examples=3
)
```

#### 1.3 SQL验证 (validation)

**文件位置**: `app/agent/text2sql/validation/`

**功能**: 对生成的SQL进行多维度验证，确保质量。

**组件**:
- `SyntaxChecker`: 语法检查（括号匹配、引号匹配、关键字）
- `SemanticChecker`: 语义检查（问题与SQL意图匹配度）
- `SQLValidator`: 整合验证器，计算综合得分

**验证维度**:
1. **语法验证**: 检查SQL语法正确性
   - 括号匹配
   - 引号匹配
   - 关键字使用
   - 危险操作警告

2. **语义验证**: 检查SQL是否符合问题意图
   - 向量相似度计算
   - 关键要素匹配（时间、数量、分组、排序）
   - 综合评分

3. **Schema验证**: 检查SQL中的表和字段是否存在

**验证结果**:
```python
{
    "valid": True/False,
    "score": 0.85,
    "passed_checks": ["syntax", "semantic"],
    "failed_checks": [...],
    "feedback": "SQL验证通过",
    "details": {...}
}
```

**使用示例**:
```python
from agent.text2sql.validation import validate_sql

result = validate_sql(
    question="查询昨天的工单量",
    sql="SELECT COUNT(*) FROM tickets WHERE created_at >= '2024-01-21'",
    schema={"tables": [...]},
    db_type="mysql"
)
```

#### 1.4 迭代生成器 (generation)

**文件位置**: `app/agent/text2sql/generation/`

**功能**: 带验证的SQL生成，支持失败后自动重试。

**组件**:
- `IterativeGenerator`: 迭代生成器
- `GenerationResult`: 生成结果

**生成流程**:
```
第1次尝试
    ↓
生成SQL → 验证
    ↓
验证失败？
    ↓ 是
构建反馈Prompt
    ↓
第2次尝试
    ↓
...（最多3次）
    ↓
返回最佳结果
```

**使用示例**:
```python
from agent.text2sql.generation import generate_with_validation

def generate_sql(question):
    # 调用LLM生成SQL
    return llm.generate(question)

result = generate_with_validation(
    question="查询昨天的工单量",
    generate_func=generate_sql,
    schema={...},
    max_retries=3
)
```

### 2. 聊天服务 (chat_service)

**文件位置**: `app/chat_service/`

**功能**: 提供对话式NL2SQL服务，管理会话和消息历史。

**组件**:
- `ChatService`: 聊天服务主类
- `ContextBuilder`: 上下文构建器，准备候选内容
- `ChatStorage`: 数据存储（SQLite）

**上下文构建流程**:
```
用户问题
    ↓
按数据源查询候选术语（20个）
    ↓
按数据源查询候选SQL示例（10个）
    ↓
发送到算法端
    ↓
算法端向量精排
    ↓
使用精排结果生成SQL
```

### 3. 向量存储 (vector_store)

**文件位置**: `app/rag/vector_store/`

**功能**: 提供向量检索能力，支持语义搜索。

**组件**:
- `ChromaVectorStore`: ChromaDB向量存储
- `EmbeddingModel`: 嵌入模型封装
- `UnifiedRetriever`: 统一检索器

**支持的检索类型**:
- Schema检索
- SQL示例检索
- 术语检索

### 4. 数据同步 (rag/sync)

**文件位置**: `app/rag/sync/`

**功能**: 同步业务数据库和向量数据库。

**组件**:
- `SyncManager`: 同步管理器
- `TerminologySync`: 术语同步
- `SQLExampleSync`: SQL示例同步
- `SchemaSync`: Schema同步
- `DatasourceConnector`: 数据源连接器

**同步触发时机**:
1. 首次连接数据源时自动同步Schema
2. 添加术语时自动同步到向量库
3. 添加SQL示例时自动同步到向量库

## SQL生成完整流程

```
┌─────────────────────────────────────────────────────────────────┐
│                        SQL生成流程                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. 问题改写                                                     │
│     输入: "请帮我查一下昨天的工单量"                              │
│     输出: "查询2024-01-21的工单量"                               │
│                                                                 │
│  2. 后端准备候选内容                                              │
│     - 查询术语表（按数据源筛选）                                   │
│     - 查询SQL示例表（按数据源筛选）                                │
│     - 发送到算法端                                                │
│                                                                 │
│  3. 向量精排（算法端）                                            │
│     - 计算问题与候选术语的相似度                                   │
│     - 计算问题与候选SQL示例的相似度                                │
│     - 选择Top 5术语 + Top 3 SQL示例                               │
│                                                                 │
│  4. Schema检索                                                   │
│     - 向量检索相关表结构                                          │
│     - 格式化为M-Schema                                            │
│                                                                 │
│  5. SQL生成                                                      │
│     - 构建Prompt（包含精排后的术语、示例、Schema）                  │
│     - 调用LLM生成SQL                                              │
│                                                                 │
│  6. SQL验证                                                      │
│     - 语法检查                                                    │
│     - 语义匹配检查                                                │
│     - Schema检查                                                  │
│     - 计算综合得分                                                │
│                                                                 │
│  7. 返回结果                                                     │
│     - SQL语句                                                     │
│     - 验证信息（得分、通过的检查、反馈）                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 配置说明

### 环境变量

```bash
# 向量存储配置
CHROMA_DB_PATH=./data/chroma_db
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# LLM配置
LLM_MODEL=gpt-4
LLM_TEMPERATURE=0.0

# 数据库配置
DATABASE_URL=sqlite:///data/aix_db.db
```

### 依赖安装

```bash
# 基础依赖
pip install chromadb sentence-transformers

# 开发依赖
pip install pytest black flake8
```

## 性能优化

### 1. 缓存机制

- **模板缓存**: YAML模板使用`@cache`装饰器缓存
- **向量缓存**: 嵌入结果可缓存避免重复计算
- **Schema缓存**: 数据库Schema缓存避免频繁查询

### 2. 异步处理

- 向量检索使用异步IO
- LLM调用支持并发
- 数据库操作使用连接池

### 3. 降级策略

- 向量检索失败时降级到传统检索
- 精排失败时使用原始候选内容
- 验证失败时仍返回生成的SQL

## 错误处理

### 常见错误

1. **向量检索失败**
   - 原因: ChromaDB未初始化或模型未下载
   - 处理: 降级到传统检索

2. **精排失败**
   - 原因: 嵌入模型加载失败
   - 处理: 使用原始候选内容

3. **验证失败**
   - 原因: SQL语法错误或语义不匹配
   - 处理: 记录警告，仍返回SQL

## 扩展指南

### 添加新的数据库支持

1. 在`template/yaml/sql_examples/`添加新的YAML模板
2. 在`template_loader.py`的`DB_TYPE_TO_TEMPLATE_NAME`中添加映射
3. 在`schema_formatter.py`的`NEED_SCHEMA_TYPES`中添加类型

### 添加新的验证规则

1. 在`validation/`目录下创建新的检查器
2. 在`SQLValidator.validate()`中调用新检查器
3. 更新验证得分权重

### 自定义问题改写规则

1. 在`rewrite/question_rewriter.py`中添加新的改写规则
2. 在`FILLER_WORDS`中添加新的填充词
3. 在`TimeNormalizer.RELATIVE_PATTERNS`中添加新的时间模式

## 测试

### 运行测试

```bash
# 运行所有测试
pytest

# 运行特定模块测试
pytest tests/test_rewrite.py
pytest tests/test_validation.py
pytest tests/test_ranking.py
```

### 测试数据

```python
# 示例测试数据
test_cases = [
    {
        "question": "查询昨天的工单量",
        "expected_sql": "SELECT COUNT(*) FROM tickets WHERE created_at >= '2024-01-21'",
        "schema": {
            "tables": [
                {"name": "tickets", "columns": ["id", "created_at"]}
            ]
        }
    }
]
```

## 监控与日志

### 关键指标

- SQL生成成功率
- 验证通过率
- 平均响应时间
- 向量检索命中率

### 日志级别

- `INFO`: 正常流程日志
- `WARNING`: 降级和恢复日志
- `ERROR`: 错误和异常日志
- `DEBUG`: 详细调试信息

## 版本历史

### v1.0.0 (2024-01)

- 初始版本，基础NL2SQL功能
- 支持MySQL、PostgreSQL

### v1.1.0 (2024-02)

- 添加向量检索功能
- 支持术语和SQL示例管理

### v1.2.0 (2024-03)

- 添加问题改写模块
- 添加向量精排功能
- 添加SQL验证模块
- 添加迭代生成器

---

**维护者**: Aix-DB Team  
**最后更新**: 2024-03
