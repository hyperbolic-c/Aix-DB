"""
聊天服务数据模型
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """聊天消息模型"""
    id: Optional[int] = None
    session_id: Optional[int] = None
    role: str = Field(..., description="角色: user, assistant")
    content: str = Field(..., description="消息内容")
    sql: Optional[str] = Field(None, description="相关的SQL语句")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, str]:
        """转换为字典格式（用于API）"""
        return {
            "role": self.role,
            "content": self.content,
        }


class ChatSession(BaseModel):
    """聊天会话模型"""
    id: Optional[int] = None
    title: str = Field(default="新会话", description="会话标题")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    message_count: int = 0


class CreateSessionRequest(BaseModel):
    """创建会话请求"""
    title: Optional[str] = None


class SendMessageRequest(BaseModel):
    """发送消息请求"""
    question: str = Field(..., description="用户问题")


class SessionResponse(BaseModel):
    """会话响应"""
    id: int
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int


class HistoryResponse(BaseModel):
    """历史记录响应"""
    session_id: int
    messages: List[ChatMessage]


class Terminology(BaseModel):
    """术语模型"""
    id: Optional[int] = None
    term: str = Field(..., description="术语名称")
    description: str = Field(..., description="术语解释")
    category: Optional[str] = Field(None, description="分类")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SqlExample(BaseModel):
    """SQL示例模型"""
    id: Optional[int] = None
    question: str = Field(..., description="用户问题")
    sql: str = Field(..., description="对应的SQL语句")
    description: Optional[str] = Field(None, description="示例描述")
    datasource_id: Optional[int] = Field(None, description="数据源ID")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CreateTerminologyRequest(BaseModel):
    """创建术语请求"""
    term: str
    description: str
    category: Optional[str] = None


class UpdateTerminologyRequest(BaseModel):
    """更新术语请求"""
    term: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None


class CreateSqlExampleRequest(BaseModel):
    """创建SQL示例请求"""
    question: str
    sql: str
    description: Optional[str] = None
    datasource_id: Optional[int] = None


class UpdateSqlExampleRequest(BaseModel):
    """更新SQL示例请求"""
    question: Optional[str] = None
    sql: Optional[str] = None
    description: Optional[str] = None
    datasource_id: Optional[int] = None
