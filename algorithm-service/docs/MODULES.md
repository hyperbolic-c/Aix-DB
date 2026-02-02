# 算法模块详细文档

## 模块概览

```
app/
├── agent/
│   └── text2sql/
│       ├── rewrite/              # 问题改写模块
│       │   ├── __init__.py
│       │   ├── question_rewriter.py
│       │   └── time_normalizer.py
│       ├── ranking/              # 向量精排模块
│       │   ├── __init__.py
│       │   └── vector_ranker.py
│       ├── validation/           # SQL验证模块
│       │   ├── __init__.py
│       │   ├── sql_validator.py
│       │   ├── syntax_checker.py
│       │   └── semantic_checker.py
│       ├── generation/           # 迭代生成模块
│       │   ├── __init__.py
│       │   └── iterative_generator.py
│       ├── sql/                  # SQL生成
│       │   ├── __init__.py
│       │   └── generator.py
│       ├── state/                # 状态管理
│       │   └── agent_state.py
│       └── template/             # 模板系统
│           ├── __init__.py
│           ├── prompt_builder.py
│           ├── schema_formatter.py
│           └── template_loader.py
├── chat_service/                 # 聊天服务
│   ├── __init__.py
│   ├── service.py
│   ├── storage.py
│   ├── context_builder.py
│   └── models.py
└── rag/                          # RAG系统
    ├── sync/                     # 数据同步
    │   ├── __init__.py
    │   ├── sync_manager.py
    │   ├── terminology_sync.py
    │   ├── sql_example_sync.py
    │   ├── schema_sync.py
    │   └── datasource_connector.py
    └── vector_store/             # 向量存储
        ├── __init__.py
        ├── chroma_store.py
        ├── embeddings.py
        └── unified_retriever.py
```

---

## 1. 问题改写模块 (rewrite)

### 1.1 QuestionRewriter

**文件**: `app/agent/text2sql/rewrite/question_rewriter.py`

**功能**: 对用户问题进行轻量级规范化改写

**核心方法**:
```python
class QuestionRewriter:
    def rewrite(self, question: str) -> str:
        """改写问题，返回规范化后的文本"""
        
    def _remove_filler_words(self, text: str) -> str:
        """去除填充词"""
        
    def _normalize_punctuation(self, text: str) -> str:
        """标准化标点符号"""
```

**配置项**:
```python
FILLER_WORDS = [
    r'请帮我', r'请', r'帮我', r'帮我查',
    r'能不能', r'能不能查', r'可以', r'可以查',
    r'我想知道', r'我想查', r'我要查',
    r'麻烦', r'麻烦你', r'麻烦查',
    r'需要', r'需要查',
    r'看看', r'看一下', r'查一下',
]
```

**使用示例**:
```python
from agent.text2sql.rewrite import QuestionRewriter

rewriter = QuestionRewriter()
result = rewriter.rewrite("请帮我查一下昨天的工单量")
# 输出: "查询2024-01-21的工单量"
```

### 1.2 TimeNormalizer

**文件**: `app/agent/text2sql/rewrite/time_normalizer.py`

**功能**: 将自然语言时间表达式转换为标准日期格式

**支持的时间模式**:
```python
RELATIVE_PATTERNS = {
    r'今天|今日|这天': 0,                    # 当天
    r'昨天|昨日|上一天': -1,                 # 昨天
    r'前天|前日': -2,                       # 前天
    r'明天|明日': 1,                        # 明天
    r'上周|上星期|上个星期': -7,             # 上周
    r'本周|这星期|本星期': 0,               # 本周
    r'最近7天|近7天|近一周|最近一周': -7,     # 最近7天
    r'最近30天|近30天|近一个月|最近一个月': -30,  # 最近30天
    r'上个月|上月': -30,                    # 上个月
    r'本月|这个月': 0,                      # 本月
}
```

**核心方法**:
```python
class TimeNormalizer:
    def normalize(self, text: str) -> str:
        """标准化文本中的时间表达式"""
        
    def _normalize_days_ago(self, text: str) -> str:
        """处理'X天前'格式"""
        
    def _normalize_month_day(self, text: str) -> str:
        """处理'X月X日'格式"""
        
    def extract_date_range(self, text: str) -> Optional[Tuple[str, str]]:
        """提取日期范围"""
```

**使用示例**:
```python
from agent.text2sql.rewrite import TimeNormalizer

normalizer = TimeNormalizer()
result = normalizer.normalize("查询昨天的工单量")
# 输出: "查询2024-01-21的工单量"

# 提取日期范围
range_result = normalizer.extract_date_range("查询最近7天的数据")
# 输出: ("2024-01-14", "2024-01-21")
```

---

## 2. 向量精排模块 (ranking)

### 2.1 VectorRanker

**文件**: `app/agent/text2sql/ranking/vector_ranker.py`

**功能**: 对候选术语和SQL示例进行向量相似度精排

**核心方法**:
```python
class VectorRanker:
    def rank_terminologies(
        self,
        question: str,
        candidates: List[Dict[str, Any]],
        top_k: int = 5
    ) -> List[RankedItem]:
        """对候选术语进行向量精排"""
        
    def rank_sql_examples(
        self,
        question: str,
        candidates: List[Dict[str, Any]],
        top_k: int = 3
    ) -> List[RankedItem]:
        """对候选SQL示例进行向量精排"""
        
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
```

**RankedItem结构**:
```python
@dataclass
class RankedItem:
    item: Dict[str, Any]    # 原始候选项
    score: float            # 相似度分数
    rank: int               # 排名
```

**使用示例**:
```python
from agent.text2sql.ranking import VectorRanker

ranker = VectorRanker()

# 精排术语
terms = [
    {"term": "工单量", "description": "工单数量"},
    {"term": "回访量", "description": "回访次数"},
]
ranked_terms = ranker.rank_terminologies(
    question="查询昨天的工单",
    candidates=terms,
    top_k=2
)

for item in ranked_terms:
    print(f"{item.rank}. {item.item['term']} (得分: {item.score:.2f})")
```

---

## 3. SQL验证模块 (validation)

### 3.1 SyntaxChecker

**文件**: `app/agent/text2sql/validation/syntax_checker.py`

**功能**: 检查SQL语句的语法正确性

**检查项**:
1. 基本结构检查（必须以SELECT/INSERT/UPDATE/DELETE开头）
2. 括号匹配检查
3. 引号匹配检查
4. 关键字检查（危险操作警告）
5. 数据库特定检查（如MySQL的LIMIT语法）

**核心方法**:
```python
class SyntaxChecker:
    def check(self, sql: str, db_type: str = "mysql") -> dict:
        """
        检查SQL语法
        
        Returns:
            {
                "valid": bool,
                "error": str or None,
                "warnings": List[str],
                "details": {
                    "structure_ok": bool,
                    "parentheses_ok": bool,
                    "quotes_ok": bool
                }
            }
        """
```

**使用示例**:
```python
from agent.text2sql.validation import check_syntax

result = check_syntax("SELECT * FROM users WHERE id = 1", db_type="mysql")
print(f"语法正确: {result['valid']}")
if result['warnings']:
    print(f"警告: {result['warnings']}")
```

### 3.2 SemanticChecker

**文件**: `app/agent/text2sql/validation/semantic_checker.py`

**功能**: 检查SQL语句与用户问题的语义匹配度

**检查维度**:
1. SQL意图提取（查询、插入、更新、删除）
2. 向量相似度计算（问题 vs SQL意图）
3. 关键要素匹配（时间、数量、分组、排序）

**核心方法**:
```python
class SemanticChecker:
    def check_match(
        self,
        question: str,
        sql: str,
        threshold: float = 0.6
    ) -> SemanticMatchResult:
        """
        检查问题和SQL的语义匹配度
        
        Returns:
            SemanticMatchResult(
                score=0.85,           # 匹配分数
                matched=True,         # 是否匹配
                analysis="语义匹配良好", # 分析说明
                details={...}         # 详细信息
            )
        """
```

**关键要素匹配规则**:
```python
# 时间相关
time_keywords = ['今天', '昨天', '最近', '上周', '本月', '2024', '2023']

# 数量相关
quantity_keywords = ['多少', '数量', '统计', 'count']

# 分组相关
group_keywords = ['各', '每个', '按', '分组']

# 排序相关
order_keywords = ['最高', '最低', '最多', '最少', '排名', '前']
```

### 3.3 SQLValidator

**文件**: `app/agent/text2sql/validation/sql_validator.py`

**功能**: 整合多种验证方式，提供全面的SQL质量检查

**验证流程**:
```
输入: question, sql, schema
    ↓
1. 语法检查 (权重40%)
    ↓
2. 语义检查 (权重40%)
    ↓
3. Schema检查 (权重20%)
    ↓
计算综合得分
    ↓
生成验证结果
```

**核心方法**:
```python
class SQLValidator:
    def validate(
        self,
        question: str,
        sql: str,
        schema: Optional[Dict[str, Any]] = None,
        db_type: str = "mysql"
    ) -> ValidationResult:
        """
        验证SQL
        
        Returns:
            ValidationResult(
                valid=True,              # 是否通过
                passed_checks=["syntax", "semantic"],
                failed_checks=[],
                warnings=[],
                score=0.85,              # 综合得分
                feedback="SQL验证通过",
                details={...}
            )
        """
```

**使用示例**:
```python
from agent.text2sql.validation import validate_sql

result = validate_sql(
    question="查询昨天的工单量",
    sql="SELECT COUNT(*) FROM tickets WHERE created_at >= '2024-01-21'",
    schema={"tables": [{"name": "tickets", "columns": ["id", "created_at"]}]},
    db_type="mysql"
)

print(f"验证通过: {result.valid}")
print(f"得分: {result.score:.2f}")
print(f"反馈: {result.feedback}")
```

---

## 4. 迭代生成模块 (generation)

### 4.1 IterativeGenerator

**文件**: `app/agent/text2sql/generation/iterative_generator.py`

**功能**: 带验证的SQL生成，支持失败后自动重试

**生成流程**:
```
第1次尝试
    ↓
生成SQL → 验证
    ↓
验证通过？
    ↓ 否
构建反馈Prompt（包含错误信息）
    ↓
第2次尝试
    ↓
...（最多max_retries次）
    ↓
返回最佳结果
```

**核心方法**:
```python
class IterativeGenerator:
    def generate(
        self,
        question: str,
        generate_func: Callable[[str], str],
        schema: Optional[Dict[str, Any]] = None,
        db_type: str = "mysql"
    ) -> GenerationResult:
        """
        生成SQL（带验证和重试）
        
        Args:
            question: 用户问题
            generate_func: SQL生成函数（接收问题，返回SQL）
            schema: Schema信息
            db_type: 数据库类型
            
        Returns:
            GenerationResult(
                sql="SELECT ...",      # 生成的SQL
                success=True,          # 是否成功
                attempts=2,            # 尝试次数
                final_validation=...,  # 最终验证结果
                history=[...]          # 历史记录
            )
        """
        
    def _prepare_retry(
        self,
        question: str,
        sql: str,
        validation: ValidationResult,
        attempt: int
    ) -> str:
        """准备重试的问题（添加反馈信息）"""
```

**使用示例**:
```python
from agent.text2sql.generation import generate_with_validation
from common.llm_util import get_llm

# 定义生成函数
def my_generate_func(question):
    llm = get_llm(temperature=0)
    # 构建Prompt...
    response = llm.invoke(prompt)
    return extract_sql(response.content)

# 生成SQL
result = generate_with_validation(
    question="查询昨天的工单量",
    generate_func=my_generate_func,
    schema={...},
    db_type="mysql",
    max_retries=3
)

if result.success:
    print(f"生成的SQL: {result.sql}")
    print(f"尝试次数: {result.attempts}")
else:
    print(f"生成失败，最佳尝试得分: {result.final_validation.score:.2f}")
```

---

## 5. 模板系统 (template)

### 5.1 PromptBuilder

**文件**: `app/agent/text2sql/template/prompt_builder.py`

**功能**: 根据模板系统构建各种提示词

**支持的功能**:
- SQL生成提示词
- 图表配置提示词
- 数据源选择提示词
- 权限过滤提示词
- 推荐问题生成提示词
- 动态SQL提示词
- 数据总结提示词

**核心方法**:
```python
class PromptBuilder:
    def build_sql_prompt(
        self,
        db_type: str,
        schema: str,
        question: str,
        engine: str,
        lang: str = "简体中文",
        terminologies: str = "",
        data_training: str = "",
        custom_prompt: str = "",
        enable_query_limit: bool = True,
        error_msg: str = "",
        current_time: Optional[str] = None,
        change_title: bool = False,
    ) -> Tuple[str, str]:
        """构建SQL生成提示词（系统提示词 + 用户提示词）"""
```

**使用示例**:
```python
from agent.text2sql.template import PromptBuilder

builder = PromptBuilder()

system_prompt, user_prompt = builder.build_sql_prompt(
    db_type="mysql",
    schema="【DB_ID】 database\n【Schema】\n# Table: tickets...",
    question="查询昨天的工单量",
    engine="MySQL 8.0",
    terminologies="工单量: 工单的数量",
    data_training="问题: 查询工单量\nSQL: SELECT COUNT(*) FROM tickets"
)
```

### 5.2 SchemaFormatter

**文件**: `app/agent/text2sql/template/schema_formatter.py`

**功能**: 将db_info字典格式转换为M-Schema字符串格式

**核心方法**:
```python
def format_schema_to_m_schema(
    db_info: Dict[str, Dict[str, Any]],
    db_name: str = "database",
    db_type: str = "mysql",
) -> str:
    """
    将db_info转换为M-Schema格式
    
    输入格式:
    {
        "table_name": {
            "columns": {
                "column_name": {
                    "type": "VARCHAR(255)",
                    "comment": "列注释"
                }
            },
            "table_comment": "表注释",
            "foreign_keys": ["column -> table.column"]
        }
    }
    
    输出格式:
    【DB_ID】 database
    【Schema】
    # Table: table_name, 表注释
    [
    (column_name:VARCHAR(255), 列注释)
    ]
    column -> table.column
    """

def get_database_engine_info(db_type: str, db_version: Optional[str] = None) -> str:
    """获取数据库引擎信息字符串"""
```

### 5.3 TemplateLoader

**文件**: `app/agent/text2sql/template/template_loader.py`

**功能**: YAML模板加载器，支持缓存机制

**核心方法**:
```python
class TemplateLoader:
    @staticmethod
    @cache
    def load_base_template() -> Dict[str, Any]:
        """加载基础模板（带缓存）"""
        
    @staticmethod
    @cache
    def load_sql_template(db_type: Union[str, None] = None) -> Dict[str, Any]:
        """加载数据库特定的SQL模板"""
        
    @staticmethod
    def reload_all_templates():
        """清空所有模板缓存"""
```

**支持的数据库类型**:
```python
DB_TYPE_TO_TEMPLATE_NAME = {
    "postgresql": "PostgreSQL",
    "pg": "PostgreSQL",
    "mysql": "MySQL",
    "oracle": "Oracle",
    "sqlserver": "Microsoft_SQL_Server",
    "clickhouse": "ClickHouse",
    "redshift": "AWS_Redshift",
    "elasticsearch": "Elasticsearch",
    "starrocks": "StarRocks",
    "doris": "Doris",
    "dm": "DM",
    "kingbase": "Kingbase",
    "sqlite": "SQLite",
}
```

---

## 6. 聊天服务 (chat_service)

### 6.1 ChatService

**文件**: `app/chat_service/service.py`

**功能**: 提供对话式NL2SQL服务

**核心方法**:
```python
class ChatService:
    async def process_message(
        self,
        session_id: int,
        message: str,
        datasource_id: Optional[int] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        处理用户消息（流式返回）
        
        Yields:
            {"event_type": "sql_generated", "data": {...}}
            {"event_type": "summary", "data": {...}}
            {"event_type": "error", "message": "..."}
        """
        
    def create_session(self, title: Optional[str] = None) -> ChatSession:
        """创建新会话"""
        
    def add_terminology(
        self,
        term: str,
        description: str,
        category: Optional[str] = None
    ) -> Terminology:
        """添加术语"""
        
    def add_sql_example(
        self,
        question: str,
        sql: str,
        description: Optional[str] = None,
        datasource_id: Optional[int] = None
    ) -> SqlExample:
        """添加SQL示例"""
```

### 6.2 ContextBuilder

**文件**: `app/chat_service/context_builder.py`

**功能**: 构建发送到算法服务的上下文

**核心方法**:
```python
class ContextBuilder:
    def build_context(
        self,
        question: str,
        datasource_id: Optional[int] = None,
        max_terminologies: int = 20,
        max_sql_examples: int = 10
    ) -> Dict[str, Any]:
        """
        构建上下文
        
        Returns:
            {
                "question": "...",
                "datasource_id": 1,
                "candidates": {
                    "terminologies": [...],
                    "sql_examples": [...]
                }
            }
        """
```

---

## 7. RAG系统 (rag)

### 7.1 数据同步 (sync)

#### SyncManager

**文件**: `app/rag/sync/sync_manager.py`

**功能**: 管理业务数据库和向量数据库的同步

#### TerminologySync

**文件**: `app/rag/sync/terminology_sync.py`

**功能**: 术语同步管理

```python
class TerminologySync:
    def sync_to_vector_store(self, terminology: Terminology) -> bool:
        """同步单个术语到向量库"""
        
    def sync_batch(self, terminologies: List[Terminology]) -> Dict[str, int]:
        """批量同步术语"""
```

#### SQLExampleSync

**文件**: `app/rag/sync/sql_example_sync.py`

**功能**: SQL示例同步管理

#### SchemaSync

**文件**: `app/rag/sync/schema_sync.py`

**功能**: Schema同步管理

```python
class SchemaSync:
    def sync_on_first_connect(
        self,
        datasource_id: int,
        schema_info: Dict[str, Any],
        db_session=None
    ) -> bool:
        """首次连接时同步Schema"""
```

#### DatasourceConnector

**文件**: `app/rag/sync/datasource_connector.py`

**功能**: 数据源连接器，封装连接和同步逻辑

```python
class DatasourceConnector:
    def connect_and_sync(
        self,
        datasource_id: int,
        db_info: Dict[str, Any],
        db_session=None
    ) -> bool:
        """连接数据源并同步Schema"""
```

### 7.2 向量存储 (vector_store)

#### ChromaVectorStore

**文件**: `app/rag/vector_store/chroma_store.py`

**功能**: ChromaDB向量存储封装

```python
class ChromaVectorStore:
    def add_document(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        doc_id: Optional[str] = None
    ) -> str:
        """添加文档到向量库"""
        
    def similarity_search(
        self,
        query: str,
        top_k: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[Document, float]]:
        """相似度搜索"""
```

#### EmbeddingModel

**文件**: `app/rag/vector_store/embeddings.py`

**功能**: 嵌入模型封装

```python
class EmbeddingModel:
    def embed_query(self, text: str) -> List[float]:
        """将文本转换为向量"""
        
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """批量转换文本为向量"""
```

---

## 模块依赖关系

```
rewrite
    └── time_normalizer

ranking
    └── embeddings (from vector_store)

validation
    ├── syntax_checker
    ├── semantic_checker
        └── embeddings (from vector_store)
    └── sql_validator
        ├── syntax_checker
        └── semantic_checker

generation
    ├── validation
    └── rewrite

sql/generator
    ├── rewrite
    ├── ranking
    ├── validation (可选)
    └── template
        ├── prompt_builder
        ├── schema_formatter
        └── template_loader

chat_service
    ├── context_builder
    └── storage

rag/sync
    ├── vector_store
    └── storage (from chat_service)
```

---

**更多文档**:
- [架构设计](ARCHITECTURE.md)
- [使用指南](USAGE.md)
- [API文档](API.md)
