# NL2SQL 系统重构设计文档

> 本文档记录了 Aix-DB 算法服务的重构设计，可作为类似 NL2SQL 项目的参考。

---

## 1. 项目背景

### 1.1 原始架构的问题

在重构之前，系统面临以下挑战：

| 问题 | 影响 | 表现 |
|------|------|------|
| 依赖历史问题质量 | 首次会话无历史数据 | 新用户体验差 |
| SQL示例常为空 | 缺乏参考示例 | 生成质量不稳定 |
| 无问题改写 | 用户表达不规范 | 检索效果差 |
| 无SQL验证 | 生成错误SQL | 执行失败率高 |
| 无迭代优化 | 一次生成定结果 | 无法自我修正 |

### 1.2 核心洞察

> **最终决定问题质量的指标还是基于该问题生成的SQL是否正确且符合用户问题。**

这意味着：
- 不应过度依赖历史问题
- 应专注于提升单次生成的质量
- 需要建立有效的质量评估机制

---

## 2. 重构目标

### 2.1 设计原则

1. **轻量级改写**：不过度改变用户原意，仅做规范化处理
2. **向量精排**：后端提供候选，算法端做精细化排序
3. **多维度验证**：语法、语义、Schema三重检查
4. **迭代优化**：验证失败时自动重试并修正

### 2.2 关键指标

| 指标 | 目标 | 说明 |
|------|------|------|
| SQL生成成功率 | > 90% | 语法正确的SQL比例 |
| 语义匹配度 | > 0.7 | 问题与SQL的匹配得分 |
| 首次生成成功率 | > 70% | 无需重试的比例 |
| 平均响应时间 | < 3s | 端到端响应时间 |

---

## 3. 架构设计

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         NL2SQL 系统架构                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐ │
│  │   用户输入   │───▶│  问题改写    │───▶│   候选内容检索       │ │
│  │             │    │ (轻量级)    │    │  (术语+SQL示例)     │ │
│  └─────────────┘    └─────────────┘    └─────────────────────┘ │
│                                                   │             │
│                                                   ▼             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐ │
│  │   结果输出   │◀───│  SQL执行    │◀───│    SQL生成          │ │
│  │             │    │             │    │  (Prompt+LLM)       │ │
│  └─────────────┘    └─────────────┘    └─────────────────────┘ │
│                                                   ▲             │
│                                                   │             │
│                              ┌────────────────────┘             │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐ │
│  │  验证失败?   │───▶│  构建反馈   │───▶│    SQL验证          │ │
│  │  (重试<3次)  │    │  Prompt     │    │  (语法+语义+Schema) │ │
│  └─────────────┘    └─────────────┘    └─────────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 核心流程

```
用户问题: "请帮我查一下昨天的工单量"
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. 问题改写                                                  │
│    - 去除填充词: "请帮我查一下" → "查询"                      │
│    - 时间标准化: "昨天" → "2024-01-21"                       │
│    输出: "查询2024-01-21的工单量"                            │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. 候选内容准备 (后端)                                        │
│    - 查询术语表: 获取20个相关术语                             │
│    - 查询SQL示例: 获取10个相关示例                            │
│    - 发送到算法端                                             │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. 向量精排 (算法端)                                          │
│    - 计算问题与术语的相似度                                   │
│    - 计算问题与SQL示例的相似度                                │
│    - 选择Top 5术语 + Top 3 SQL示例                            │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Schema检索                                                │
│    - 向量检索相关表结构                                       │
│    - 格式化为M-Schema                                        │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. SQL生成                                                   │
│    - 构建Prompt (术语+示例+Schema)                            │
│    - 调用LLM生成SQL                                          │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. SQL验证                                                   │
│    - 语法检查: 括号、引号、关键字                             │
│    - 语义检查: 问题与SQL意图匹配度                            │
│    - Schema检查: 表和字段存在性                               │
│    - 计算综合得分                                            │
└─────────────────────────────────────────────────────────────┘
    │
    ├─ 验证通过 (得分≥0.7) ──▶ 返回SQL
    │
    └─ 验证失败 ──▶ 构建反馈Prompt ──▶ 重新生成 (最多3次)
```

---

## 4. 核心模块设计

### 4.1 问题改写模块 (Rewrite)

**设计思路**：轻量级改写，保留原意，提高规范性

```python
class QuestionRewriter:
    """
    问题改写器 - 轻量级规范化
    
    原则：
    1. 不改变用户核心意图
    2. 仅做标准化处理
    3. 保持简洁明了
    """
    
    def rewrite(self, question: str) -> str:
        # 1. 去除填充词
        text = self._remove_filler_words(question)
        # 2. 标准化时间
        text = self._normalize_time(text)
        # 3. 标准化标点
        text = self._normalize_punctuation(text)
        return text
```

**关键设计决策**：
- **不做语义扩展**：避免引入歧义
- **保留专业术语**：不改写业务词汇
- **时间标准化**：将相对时间转为绝对日期，便于检索

### 4.2 向量精排模块 (Ranking)

**设计思路**：后端粗筛，算法端精排，分离关注点

```python
class VectorRanker:
    """
    向量精排器 - 精细化排序候选内容
    
    为什么后端不直接排序？
    1. 后端无法获取用户问题的向量表示
    2. 算法端可以使用更复杂的排序策略
    3. 便于后续扩展重排序模型
    """
    
    def rank_terminologies(
        self,
        question: str,
        candidates: List[Dict],
        top_k: int = 5
    ) -> List[RankedItem]:
        # 1. 生成问题向量
        query_vec = self.embeddings.embed_query(question)
        
        # 2. 计算相似度
        scored = []
        for candidate in candidates:
            content = f"{candidate['term']}: {candidate['description']}"
            candidate_vec = self.embeddings.embed_query(content)
            score = cosine_similarity(query_vec, candidate_vec)
            scored.append(RankedItem(candidate, score))
        
        # 3. 排序返回Top K
        return sorted(scored, key=lambda x: x.score, reverse=True)[:top_k]
```

**关键设计决策**：
- **后端提供候选**：按数据源筛选，减少算法端负担
- **算法端精排**：基于语义相似度，更精准
- **可配置Top K**：灵活调整候选数量

### 4.3 SQL验证模块 (Validation)

**设计思路**：多维度验证，综合评分，提供反馈

```python
class SQLValidator:
    """
    SQL验证器 - 多维度质量检查
    
    验证维度：
    1. 语法：SQL是否正确
    2. 语义：是否符合问题意图
    3. Schema：表和字段是否存在
    """
    
    def validate(self, question: str, sql: str, schema: dict) -> ValidationResult:
        # 1. 语法检查 (权重40%)
        syntax_result = self.syntax_checker.check(sql)
        
        # 2. 语义检查 (权重40%)
        semantic_result = self.semantic_checker.check_match(question, sql)
        
        # 3. Schema检查 (权重20%)
        schema_result = self._check_schema(sql, schema)
        
        # 4. 计算综合得分
        score = (
            syntax_score * 0.4 +
            semantic_score * 0.4 +
            schema_score * 0.2
        )
        
        # 5. 生成反馈
        feedback = self._generate_feedback(syntax_result, semantic_result, schema_result)
        
        return ValidationResult(
            valid=score >= 0.7,
            score=score,
            feedback=feedback,
            details={...}
        )
```

**关键设计决策**：
- **语法检查优先**：语法错误直接判定失败
- **语义检查使用向量**：计算问题与SQL意图的相似度
- **权重可配置**：适应不同场景需求
- **提供详细反馈**：便于迭代优化

### 4.4 迭代生成模块 (Generation)

**设计思路**：验证驱动，反馈循环，自我修正

```python
class IterativeGenerator:
    """
    迭代生成器 - 带验证的SQL生成
    
    流程：
    生成 → 验证 → 反馈 → 重试 (最多3次)
    """
    
    def generate(
        self,
        question: str,
        generate_func: Callable,
        max_retries: int = 3
    ) -> GenerationResult:
        history = []
        
        for attempt in range(max_retries):
            # 1. 生成SQL
            sql = generate_func(question)
            
            # 2. 验证SQL
            validation = self.validator.validate(question, sql)
            
            # 3. 记录历史
            history.append({"sql": sql, "validation": validation})
            
            # 4. 检查是否通过
            if validation.valid:
                return GenerationResult(
                    sql=sql,
                    success=True,
                    attempts=attempt + 1,
                    final_validation=validation
                )
            
            # 5. 准备重试
            question = self._prepare_retry(question, sql, validation, attempt)
        
        # 6. 返回最佳结果
        best = max(history, key=lambda x: x["validation"].score)
        return GenerationResult(
            sql=best["sql"],
            success=False,
            attempts=max_retries,
            final_validation=best["validation"]
        )
```

**关键设计决策**：
- **反馈Prompt构建**：将验证错误信息融入Prompt
- **保留历史**：便于分析和优化
- **返回最佳结果**：即使失败也给出最接近的答案
- **限制重试次数**：避免无限循环

---

## 5. 数据流设计

### 5.1 术语和SQL示例管理

```
┌─────────────────────────────────────────────────────────────┐
│                    数据同步流程                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  业务数据库 (SQLite)          向量数据库 (ChromaDB)          │
│  ┌─────────────────┐          ┌─────────────────┐          │
│  │  terminologies  │          │  terminologies  │          │
│  │  - id           │◀────────▶│  - content      │          │
│  │  - term         │  同步     │  - metadata     │          │
│  │  - description  │          │  - embedding    │          │
│  │  - category     │          │                 │          │
│  └─────────────────┘          └─────────────────┘          │
│                                                             │
│  ┌─────────────────┐          ┌─────────────────┐          │
│  │  sql_examples   │          │  sql_examples   │          │
│  │  - id           │◀────────▶│  - content      │          │
│  │  - question     │  同步     │  - metadata     │          │
│  │  - sql          │          │  - embedding    │          │
│  │  - datasource_id│          │                 │          │
│  └─────────────────┘          └─────────────────┘          │
│                                                             │
│  同步触发时机：                                               │
│  1. 添加/更新术语时自动同步                                   │
│  2. 添加/更新SQL示例时自动同步                                │
│  3. 首次连接数据源时同步Schema                                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 候选内容检索流程

```
用户问题: "查询昨天的工单量"
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 后端 (Java/Node.js)                                          │
│                                                              │
│  1. 查询术语表                                               │
│     SELECT * FROM terminologies                              │
│     WHERE category = 'metrics'                               │
│     LIMIT 20                                                 │
│                                                              │
│  2. 查询SQL示例                                              │
│     SELECT * FROM sql_examples                               │
│     WHERE datasource_id = 1                                  │
│     LIMIT 10                                                 │
│                                                              │
│  3. 发送到算法端                                             │
│     POST /api/text2sql                                       │
│     {                                                        │
│       "question": "查询昨天的工单量",                         │
│       "candidates": {                                        │
│         "terminologies": [...],                              │
│         "sql_examples": [...]                                │
│       }                                                      │
│     }                                                        │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 算法端 (Python)                                              │
│                                                              │
│  4. 向量精排                                                 │
│     - 计算问题与每个术语的相似度                              │
│     - 计算问题与每个SQL示例的相似度                           │
│     - 选择Top 5术语 + Top 3 SQL示例                          │
│                                                              │
│  5. 构建Prompt                                               │
│     - 使用精排后的术语和示例                                  │
│     - 结合Schema信息                                         │
│     - 调用LLM生成SQL                                         │
└─────────────────────────────────────────────────────────────┘
```

---

## 6. 关键技术决策

### 6.1 为什么使用轻量级改写？

| 方案 | 优点 | 缺点 | 选择 |
|------|------|------|------|
| 重量级改写 (LLM) | 改写质量高 | 成本高、延迟大、可能改变原意 | ❌ |
| 轻量级改写 (规则) | 快速、成本低、保留原意 | 改写能力有限 | ✅ |
| 不改写 | 简单 | 检索效果差 | ❌ |

**决策理由**：
1. NL2SQL的核心是理解用户意图，不是改写问题
2. 过度改写可能引入歧义
3. 轻量级改写足以提升检索效果

### 6.2 为什么后端不直接排序？

| 方案 | 优点 | 缺点 | 选择 |
|------|------|------|------|
| 后端排序 | 减少数据传输 | 无法语义排序、算法端无法优化 | ❌ |
| 算法端精排 | 语义精准、可扩展 | 需要传输候选数据 | ✅ |

**决策理由**：
1. 向量排序需要嵌入模型，后端部署成本高
2. 算法端可以使用更复杂的排序策略
3. 候选数据量可控（20术语+10示例），传输开销小

### 6.3 为什么需要SQL验证？

| 方案 | 优点 | 缺点 | 选择 |
|------|------|------|------|
| 直接执行 | 简单 | 错误SQL导致执行失败 | ❌ |
| 语法验证 | 避免语法错误 | 无法发现语义错误 | ❌ |
| 多维度验证 | 全面检查 | 实现复杂 | ✅ |

**决策理由**：
1. 执行失败用户体验差
2. 语义错误比语法错误更常见
3. 验证反馈可用于迭代优化

### 6.4 为什么使用迭代生成？

| 方案 | 优点 | 缺点 | 选择 |
|------|------|------|------|
| 单次生成 | 快速 | 错误无法修正 | ❌ |
| 迭代生成 | 可自我修正 | 可能增加延迟 | ✅ |

**决策理由**：
1. 首次生成成功率约70%，有优化空间
2. 验证反馈提供了明确的优化方向
3. 限制重试次数（3次），控制延迟

---

## 7. 实现细节

### 7.1 问题改写实现

```python
# app/agent/text2sql/rewrite/question_rewriter.py

class QuestionRewriter:
    """问题改写器"""
    
    # 填充词列表 - 可配置
    FILLER_WORDS = [
        r'请帮我', r'请', r'帮我', r'帮我查',
        r'能不能', r'能不能查', r'可以', r'可以查',
        r'我想知道', r'我想查', r'我要查',
        r'麻烦', r'麻烦你', r'麻烦查',
        r'需要', r'需要查',
        r'看看', r'看一下', r'查一下',
    ]
    
    def rewrite(self, question: str) -> str:
        """改写问题"""
        text = question
        
        # 1. 去除填充词
        text = self._remove_filler_words(text)
        
        # 2. 标准化时间
        text = self.time_normalizer.normalize(text)
        
        # 3. 标准化标点
        text = self._normalize_punctuation(text)
        
        return text.strip()
```

### 7.2 向量精排实现

```python
# app/agent/text2sql/ranking/vector_ranker.py

class VectorRanker:
    """向量精排器"""
    
    def __init__(self):
        self.embeddings = EmbeddingModel()
    
    def rank_terminologies(
        self,
        question: str,
        candidates: List[Dict],
        top_k: int = 5
    ) -> List[RankedItem]:
        """精排术语"""
        if not candidates:
            return []
        
        # 生成问题向量
        query_vec = self.embeddings.embed_query(question)
        
        # 计算相似度
        scored_items = []
        for candidate in candidates:
            # 构建术语文本
            content = candidate['term']
            if candidate.get('description'):
                content += f"\n{candidate['description']}"
            
            # 生成向量并计算相似度
            candidate_vec = self.embeddings.embed_query(content)
            score = self._cosine_similarity(query_vec, candidate_vec)
            
            scored_items.append(RankedItem(
                item=candidate,
                score=score,
                rank=0  # 稍后设置
            ))
        
        # 排序并设置排名
        scored_items.sort(key=lambda x: x.score, reverse=True)
        for i, item in enumerate(scored_items[:top_k], 1):
            item.rank = i
        
        return scored_items[:top_k]
```

### 7.3 SQL验证实现

```python
# app/agent/text2sql/validation/sql_validator.py

class SQLValidator:
    """SQL验证器"""
    
    def __init__(self):
        self.syntax_checker = SyntaxChecker()
        self.semantic_checker = SemanticChecker()
    
    def validate(
        self,
        question: str,
        sql: str,
        schema: Optional[Dict] = None,
        db_type: str = "mysql"
    ) -> ValidationResult:
        """验证SQL"""
        passed = []
        failed = []
        
        # 1. 语法检查 (权重40%)
        syntax_result = self.syntax_checker.check(sql, db_type)
        if syntax_result["valid"]:
            passed.append("syntax")
            syntax_score = 1.0
        else:
            failed.append({"check": "syntax", "error": syntax_result["error"]})
            syntax_score = 0.0
        
        # 2. 语义检查 (权重40%)
        semantic_result = self.semantic_checker.check_match(question, sql)
        if semantic_result.matched:
            passed.append("semantic")
        else:
            failed.append({
                "check": "semantic",
                "error": semantic_result.analysis,
                "score": semantic_result.score
            })
        semantic_score = semantic_result.score
        
        # 3. Schema检查 (权重20%)
        schema_score = 1.0
        if schema:
            schema_result = self._check_schema(sql, schema)
            if schema_result["valid"]:
                passed.append("schema")
            else:
                failed.append({"check": "schema", "error": schema_result["error"]})
                schema_score = 0.0
        
        # 计算综合得分
        score = syntax_score * 0.4 + semantic_score * 0.4 + schema_score * 0.2
        
        # 生成反馈
        feedback = self._generate_feedback(failed, [])
        
        # 判断是否通过 (语法和Schema必须通过)
        valid = len([f for f in failed if f["check"] in ["syntax", "schema"]]) == 0
        
        return ValidationResult(
            valid=valid and score >= 0.7,
            passed_checks=passed,
            failed_checks=failed,
            warnings=[],
            score=score,
            feedback=feedback,
            details={
                "syntax": syntax_result,
                "semantic": semantic_result,
                "schema": schema_result if schema else None
            }
        )
```

### 7.4 迭代生成实现

```python
# app/agent/text2sql/generation/iterative_generator.py

class IterativeGenerator:
    """迭代生成器"""
    
    def __init__(self, validator: SQLValidator):
        self.validator = validator
    
    def generate(
        self,
        question: str,
        generate_func: Callable[[str], str],
        schema: Optional[Dict] = None,
        db_type: str = "mysql",
        max_retries: int = 3
    ) -> GenerationResult:
        """生成SQL（带验证和重试）"""
        history = []
        current_question = question
        
        for attempt in range(1, max_retries + 1):
            try:
                # 生成SQL
                sql = generate_func(current_question)
                
                # 验证SQL
                validation = self.validator.validate(
                    question=question,  # 使用原始问题验证
                    sql=sql,
                    schema=schema,
                    db_type=db_type
                )
                
                # 记录历史
                history.append({
                    "attempt": attempt,
                    "sql": sql,
                    "validation": validation
                })
                
                # 检查是否通过
                if validation.valid and validation.score >= 0.7:
                    return GenerationResult(
                        sql=sql,
                        success=True,
                        attempts=attempt,
                        final_validation=validation,
                        history=history
                    )
                
                # 准备重试
                if attempt < max_retries:
                    current_question = self._prepare_retry(
                        question, sql, validation, attempt
                    )
                    
            except Exception as e:
                logger.error(f"生成失败 (尝试 {attempt}): {e}")
                if attempt == max_retries:
                    break
        
        # 返回最佳结果
        if history:
            best = max(history, key=lambda x: x["validation"].score)
            return GenerationResult(
                sql=best["sql"],
                success=False,
                attempts=len(history),
                final_validation=best["validation"],
                history=history
            )
        
        return GenerationResult(
            sql="",
            success=False,
            attempts=max_retries,
            final_validation=None,
            history=history
        )
    
    def _prepare_retry(
        self,
        question: str,
        sql: str,
        validation: ValidationResult,
        attempt: int
    ) -> str:
        """准备重试的问题"""
        feedback_parts = [
            f"原始问题: {question}",
            f"生成的SQL: {sql}",
            f"验证结果: 得分 {validation.score:.2f}",
            f"问题: {validation.feedback}",
            "请修正SQL，确保:",
        ]
        
        # 根据失败项添加具体建议
        for failed in validation.failed_checks:
            if failed["check"] == "syntax":
                feedback_parts.append("- SQL语法正确")
            elif failed["check"] == "semantic":
                feedback_parts.append("- SQL符合问题意图")
            elif failed["check"] == "schema":
                feedback_parts.append("- 表和字段名称正确")
        
        feedback_parts.append(f"请生成修正后的SQL (重试 {attempt + 1}/3):")
        
        return "\n".join(feedback_parts)
```

---

## 8. 性能优化

### 8.1 缓存策略

```python
# 模板缓存
@cache
def load_template(db_type: str) -> Dict:
    """加载模板（带缓存）"""
    return yaml.safe_load(open(f"templates/{db_type}.yaml"))

# 向量缓存
class EmbeddingCache:
    """嵌入结果缓存"""
    
    def __init__(self, max_size: int = 1000):
        self.cache = LRUCache(maxsize=max_size)
    
    def get_or_compute(self, text: str, compute_func: Callable) -> List[float]:
        if text in self.cache:
            return self.cache[text]
        result = compute_func(text)
        self.cache[text] = result
        return result
```

### 8.2 异步处理

```python
# 异步向量检索
async def search_similar_async(
    query: str,
    collection: str,
    top_k: int = 5
) -> List[Tuple[Document, float]]:
    """异步相似度搜索"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,  # 使用默认线程池
        lambda: vector_store.similarity_search(query, top_k)
    )

# 并发LLM调用
async def generate_batch(
    questions: List[str],
    generate_func: Callable
) -> List[str]:
    """批量生成SQL"""
    tasks = [generate_func(q) for q in questions]
    return await asyncio.gather(*tasks)
```

### 8.3 降级策略

```python
class DegradationStrategy:
    """降级策略"""
    
    def rank_with_fallback(
        self,
        question: str,
        candidates: List[Dict]
    ) -> List[RankedItem]:
        try:
            # 尝试向量精排
            return self.vector_ranker.rank(question, candidates)
        except Exception as e:
            logger.warning(f"向量精排失败: {e}，降级到原始顺序")
            # 降级：返回原始顺序
            return [
                RankedItem(item=c, score=1.0 - i * 0.01, rank=i + 1)
                for i, c in enumerate(candidates[:5])
            ]
```

---

## 9. 测试策略

### 9.1 单元测试

```python
# tests/test_rewrite.py

def test_time_normalization():
    """测试时间标准化"""
    normalizer = TimeNormalizer()
    
    test_cases = [
        ("查询昨天的工单", "查询2024-01-21的工单"),
        ("查询最近7天的数据", "查询2024-01-14至2024-01-21的数据"),
    ]
    
    for input_text, expected in test_cases:
        result = normalizer.normalize(input_text)
        assert expected in result, f"期望包含'{expected}'，实际'{result}'"

# tests/test_validation.py

def test_syntax_validation():
    """测试语法验证"""
    checker = SyntaxChecker()
    
    # 正确SQL
    result = checker.check("SELECT * FROM users WHERE id = 1")
    assert result["valid"] is True
    
    # 括号不匹配
    result = checker.check("SELECT * FROM users WHERE id = (1")
    assert result["valid"] is False
    assert "括号" in result["error"]
```

### 9.2 集成测试

```python
# tests/test_integration.py

async def test_full_pipeline():
    """测试完整流程"""
    # 1. 准备数据
    state = create_test_state()
    
    # 2. 执行生成
    result = await sql_generate(state)
    
    # 3. 验证结果
    assert result["generated_sql"] is not None
    assert result["sql_validation"]["score"] >= 0.7
    
    # 4. 验证SQL可执行
    result_set = execute_sql(result["generated_sql"])
    assert result_set is not None
```

### 9.3 性能测试

```python
# tests/test_performance.py

def test_response_time():
    """测试响应时间"""
    import time
    
    start = time.time()
    result = sql_generate(create_test_state())
    elapsed = time.time() - start
    
    assert elapsed < 3.0, f"响应时间 {elapsed:.2f}s 超过3秒限制"

def test_concurrent_requests():
    """测试并发性能"""
    import asyncio
    
    async def run_concurrent():
        tasks = [sql_generate(create_test_state()) for _ in range(10)]
        results = await asyncio.gather(*tasks)
        return results
    
    results = asyncio.run(run_concurrent())
    assert len(results) == 10
    assert all(r["generated_sql"] for r in results)
```

---

## 10. 部署与运维

### 10.1 环境配置

```bash
# .env 文件
# 数据库配置
DATABASE_URL=sqlite:///data/aix_db.db

# 向量存储配置
CHROMA_DB_PATH=./data/chroma_db
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# LLM配置
LLM_MODEL=gpt-4
LLM_API_KEY=your_api_key
LLM_TEMPERATURE=0.0

# 服务配置
MAX_RETRIES=3
VALIDATION_THRESHOLD=0.7
TOP_K_TERMINOLOGIES=5
TOP_K_SQL_EXAMPLES=3
```

### 10.2 监控指标

```python
# metrics.py

from prometheus_client import Counter, Histogram, Gauge

# 计数器
sql_generation_total = Counter(
    'sql_generation_total',
    'Total SQL generation requests',
    ['status']  # success, failed
)

# 直方图
sql_generation_duration = Histogram(
    'sql_generation_duration_seconds',
    'SQL generation duration'
)

# 仪表盘
validation_score = Gauge(
    'sql_validation_score',
    'Average validation score'
)
```

### 10.3 日志规范

```python
# logging_config.py

import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler()
    ]
)

# 关键日志点
logger.info(f"问题改写: '{original}' -> '{rewritten}'")
logger.info(f"向量精排: 从{len(candidates)}个候选中选择Top {top_k}")
logger.info(f"SQL验证: 得分={score:.2f}, 通过={validation.valid}")
logger.warning(f"SQL验证失败: {validation.feedback}")
logger.error(f"生成失败: {error}")
```

---

## 11. 经验教训

### 11.1 成功的经验

1. **轻量级改写策略**
   - 不过度依赖LLM，降低成本和延迟
   - 保留用户原意，避免引入歧义
   - 规则可配置，便于业务定制

2. **分离前后端职责**
   - 后端负责数据管理和粗筛
   - 算法端负责精排和生成
   - 职责清晰，便于独立优化

3. **验证驱动开发**
   - 验证不仅是检查，更是优化手段
   - 反馈循环实现自我修正
   - 多维度评估确保质量

### 11.2 遇到的挑战

1. **语义验证的准确性**
   - 挑战：如何准确判断SQL是否符合问题意图
   - 解决：结合向量相似度和规则匹配

2. **迭代生成的延迟**
   - 挑战：多次验证增加响应时间
   - 解决：限制重试次数，异步验证

3. **向量模型的选择**
   - 挑战：中文语义理解能力
   - 解决：测试多个模型，选择最适合的

### 11.3 改进方向

1. **引入重排序模型**
   - 使用更复杂的模型进行精排
   - 考虑问题类型、数据源特征

2. **强化学习优化**
   - 基于用户反馈优化生成策略
   - 自动学习最佳Prompt模板

3. **多模态支持**
   - 支持图表、表格作为输入
   - 生成可视化SQL结果

---

## 12. 参考资源

### 12.1 相关论文

1. **Text-to-SQL Survey**
   - "A Survey on Text-to-SQL Parsing: Concepts, Methods, and Future Directions"
   - 提供了Text-toSQL的全面概述

2. **Spider Dataset**
   - "Spider: A Large-Scale Human-Labeled Dataset for Complex and Cross-Domain Semantic Parsing and Text-to-SQL Task"
   - 跨域Text-toSQL的标准数据集

3. **BIRD Benchmark**
   - "Can LLM Already Serve as A Database Interface? A BIg Bench for Large-Scale Database Grounded Text-to-SQLs"
   - 大规模真实数据库基准测试

### 12.2 开源项目

1. **Vanna**
   - https://github.com/vanna-ai/vanna
   - 简化的SQL生成框架

2. **SQLCoder**
   - https://github.com/defog-ai/sqlcoder
   - 开源Text-to-SQL模型

3. **DB-GPT**
   - https://github.com/eosphoros-ai/DB-GPT
   - 数据库AI助手框架

### 12.3 技术文档

- [LangChain Documentation](https://python.langchain.com/)
- [ChromaDB Documentation](https://docs.trychroma.com/)
- [Sentence Transformers](https://www.sbert.net/)

---

## 13. 总结

本次重构的核心思想是：**通过验证驱动的方式提升SQL生成质量**。

关键设计点：
1. **轻量级改写**：规范化用户输入，不改变原意
2. **向量精排**：后端粗筛 + 算法端精排，分离关注点
3. **多维度验证**：语法、语义、Schema三重检查
4. **迭代优化**：验证失败时自动重试并修正

这些设计使得系统：
- 不依赖历史问题质量
- 适应首次会话场景
- 提供可量化的质量评估
- 具备自我修正能力

希望本文档能为类似项目提供有价值的参考。

---

**文档版本**: 1.0  
**最后更新**: 2024-03  
**作者**: Aix-DB Team
