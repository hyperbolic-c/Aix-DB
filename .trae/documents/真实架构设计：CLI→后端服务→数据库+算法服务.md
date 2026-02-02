## 真实架构设计

### 架构流程

```
┌─────────────┐     HTTP      ┌──────────────┐     SQL      ┌─────────┐
│   CLI工具   │ ────────────→ │  后端服务    │ ───────────→ │ SQLite  │
│  (terminal) │               │  (FastAPI)   │              │ (chat)  │
└─────────────┘               └──────────────┘              └─────────┘
                                     │
                                     ↓ HTTP
                              ┌──────────────┐
                              │  算法服务    │
                              │  (Text2SQL)  │
                              └──────────────┘
```

### 模块划分

**1. 后端服务 (app/chat_service/)**
- 独立的FastAPI路由 `/chat/*`
- 管理会话和消息（SQLite存储）
- 转发请求到算法服务
- 组装多轮对话上下文

**2. CLI工具 (tools/cli/)**
- 纯HTTP客户端
- 调用后端服务API
- 终端交互展示
- 不直接接触数据库

### 数据流

```
1. CLI发送问题 → 后端 /chat/message
2. 后端查询历史 → SQLite
3. 后端组装请求（问题+历史）→ 算法服务 /analyze
4. 后端保存消息 → SQLite
5. 后端返回结果 → CLI
```

### 文件清单

**后端服务**:
1. `app/chat_service/__init__.py`
2. `app/chat_service/models.py` - 数据模型
3. `app/chat_service/storage.py` - SQLite存储
4. `app/chat_service/service.py` - 业务逻辑（调用算法服务）
5. `app/chat_service/router.py` - API路由
6. 更新 `app/main.py` - 注册路由

**CLI工具**:
1. `tools/cli/chat_client.py` - 后端服务客户端
2. 更新 `tools/cli/interactive.py` - 使用chat_client
3. 删除 `tools/cli/session_manager.py` - 移到后端

### API设计

```
# 会话管理
POST   /chat/sessions              # 创建会话
GET    /chat/sessions              # 列表
GET    /chat/sessions/{id}         # 详情
DELETE /chat/sessions/{id}         # 删除

# 消息/对话
POST   /chat/sessions/{id}/message # 发送消息（自动调用算法服务）
GET    /chat/sessions/{id}/history # 获取历史
```

### 关键特性

- CLI只与后端服务通信
- 后端服务统一管理层
- 算法服务无状态，只负责Text2SQL
- 多轮对话上下文由后端组装