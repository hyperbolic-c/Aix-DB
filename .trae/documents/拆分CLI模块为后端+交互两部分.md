## 架构重新设计

### 1. 后端模块 (app/chat/)
只实现多轮对话的核心功能，独立运行

```
app/chat/
├── __init__.py
├── models.py          # ChatSession, ChatMessage 数据模型
├── storage.py         # SQLite存储实现
├── service.py         # ChatService业务逻辑
└── router.py          # FastAPI路由 /chat/*
```

**功能**:
- 会话CRUD（创建、查询、删除）
- 消息存储和查询
- 多轮对话历史管理
- REST API接口

**独立运行**: 可以作为独立服务，也可以被主服务包含

### 2. CLI交互模块 (tools/cli/)
只负责终端交互，调用后端API

```
tools/cli/
├── __init__.py
├── client.py          # HTTP客户端（调用算法服务）
├── chat_client.py     # Chat服务客户端（新增）
├── renderer.py        # 终端渲染
├── config.py          # 配置
└── interactive.py     # 交互式终端
```

**功能**:
- 调用后端API管理会话
- 终端交互展示
- 不直接操作数据库

### 3. 文件清单

**后端模块**:
1. `app/chat/__init__.py`
2. `app/chat/models.py` - Pydantic模型
3. `app/chat/storage.py` - SQLite存储
4. `app/chat/service.py` - 业务逻辑
5. `app/chat/router.py` - API路由
6. 更新 `app/main.py` - 注册chat路由

**CLI模块**:
1. 更新 `tools/cli/chat_client.py` - 新增（调用chat API）
2. 更新 `tools/cli/interactive.py` - 使用chat_client
3. 删除 `tools/cli/session_manager.py` - 移到后端

### 4. API设计

```
POST   /chat/sessions           # 创建会话
GET    /chat/sessions           # 列表会话
GET    /chat/sessions/{id}      # 获取会话
DELETE /chat/sessions/{id}      # 删除会话
POST   /chat/sessions/{id}/messages  # 添加消息
GET    /chat/sessions/{id}/messages  # 获取历史
```

### 5. 使用流程

```
CLI工具 → HTTP API → Chat Router → Chat Service → SQLite
```

这样CLI完全不接触数据库，所有数据操作通过API完成。