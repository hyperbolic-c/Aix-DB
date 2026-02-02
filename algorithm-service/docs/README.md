# 算法服务文档

欢迎来到 Aix-DB 算法服务文档中心！

## 文档概览

| 文档 | 描述 | 适合读者 |
|------|------|----------|
| [架构设计](ARCHITECTURE.md) | 系统整体架构、模块关系、数据流 | 架构师、开发者 |
| [使用指南](USAGE.md) | 快速开始、核心功能使用、配置说明 | 开发者、运维人员 |
| [模块文档](MODULES.md) | 各模块详细说明、API参考、依赖关系 | 开发者 |
| [API文档](API.md) | RESTful API接口说明、错误码 | 前端开发者、API使用者 |

## 快速导航

### 🚀 开始使用

- [快速开始](USAGE.md#快速开始)
- [环境配置](USAGE.md#配置说明)
- [核心功能](USAGE.md#核心功能使用)

### 🏗️ 架构设计

- [整体架构](ARCHITECTURE.md#整体架构)
- [SQL生成流程](ARCHITECTURE.md#sql生成完整流程)
- [模块关系](MODULES.md#模块依赖关系)

### 📚 模块说明

- [问题改写](MODULES.md#1-问题改写模块-rewrite)
- [向量精排](MODULES.md#2-向量精排模块-ranking)
- [SQL验证](MODULES.md#3-sql验证模块-validation)
- [迭代生成](MODULES.md#4-迭代生成模块-generation)
- [模板系统](MODULES.md#5-模板系统-template)
- [聊天服务](MODULES.md#6-聊天服务-chat_service)
- [RAG系统](MODULES.md#7-rag系统-rag)

### 🔌 API接口

- [Text2SQL API](API.md#1-text2sql-api)
- [聊天服务 API](API.md#2-聊天服务-api)
- [术语管理 API](API.md#3-术语管理-api)
- [SQL示例管理 API](API.md#4-sql示例管理-api)

## 核心功能

### 1. 问题改写

将用户输入的自然语言问题进行规范化改写，提高SQL生成质量。

```python
from agent.text2sql.rewrite import rewrite_question

result = rewrite_question("请帮我查一下昨天的工单量")
# 输出: "查询2024-01-21的工单量"
```

### 2. 向量精排

对候选术语和SQL示例进行向量相似度精排，选择最相关的内容。

```python
from agent.text2sql.ranking import rank_candidates

result = rank_candidates(
    question="查询昨天的工单量",
    terminologies=[...],
    sql_examples=[...]
)
```

### 3. SQL验证

对生成的SQL进行多维度验证，确保质量。

```python
from agent.text2sql.validation import validate_sql

result = validate_sql(
    question="查询昨天的工单量",
    sql="SELECT COUNT(*) FROM tickets WHERE created_at >= '2024-01-21'"
)
```

### 4. 迭代生成

带验证的SQL生成，支持失败后自动重试。

```python
from agent.text2sql.generation import generate_with_validation

result = generate_with_validation(
    question="查询昨天的工单量",
    generate_func=my_generate_func,
    max_retries=3
)
```

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      算法服务 (algorithm-service)              │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   API层     │  │  聊天服务    │  │     向量存储         │  │
│  └──────┬──────┘  └──────┬──────┘  └─────────────────────┘  │
│         │                │                                   │
│  ┌──────┴────────────────┴─────────────────────────────────┐│
│  │                  Agent工作流 (text2sql)                   ││
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌─────────────────┐   ││
│  │  │问题改写 │ │表检索  │ │SQL生成 │ │SQL执行与总结    │   ││
│  │  └────────┘ └────────┘ └────────┘ └─────────────────┘   ││
│  └──────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────┐│
│  │                  支持模块                                ││
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌─────────────────┐   ││
│  │  │向量精排 │ │SQL验证 │ │模板系统 │ │数据服务        │   ││
│  │  └────────┘ └────────┘ └────────┘ └─────────────────┘   ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

## 最新更新

### v1.2.0 (2024-03)

- ✅ 新增问题改写模块
- ✅ 新增向量精排功能
- ✅ 新增SQL验证模块
- ✅ 新增迭代生成器
- ✅ 优化SQL生成流程

### v1.1.0 (2024-02)

- ✅ 新增向量检索功能
- ✅ 支持术语和SQL示例管理
- ✅ 支持多数据源

### v1.0.0 (2024-01)

- ✅ 初始版本
- ✅ 基础NL2SQL功能
- ✅ 支持MySQL、PostgreSQL

## 贡献指南

欢迎提交Issue和Pull Request！

### 提交Issue

- 描述清晰的问题或需求
- 提供复现步骤（如果是Bug）
- 标注相关模块

### 提交PR

1. Fork 仓库
2. 创建功能分支 (`git checkout -b feature/xxx`)
3. 提交更改 (`git commit -am 'Add xxx'`)
4. 推送到分支 (`git push origin feature/xxx`)
5. 创建 Pull Request

## 许可证

MIT License

---

**维护者**: Aix-DB Team  
**最后更新**: 2024-03
