"""
算法服务请求/响应模型定义
"""

from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class EventType(str, Enum):
    """流式响应事件类型"""
    # 步骤进度事件
    STEP_START = "step_start"
    STEP_COMPLETE = "step_complete"
    
    # 数据生成事件
    SQL_GENERATED = "sql_generated"
    SQL_FILTERED = "sql_filtered"
    SQL_EXECUTED = "sql_executed"
    CHART_GENERATED = "chart_generated"
    SUMMARY = "summary"
    RECOMMENDATIONS = "recommendations"
    
    # 状态事件
    ERROR = "error"
    COMPLETE = "complete"


class AlgorithmEvent(BaseModel):
    """算法服务流式响应事件"""
    event_type: EventType
    step_name: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    message: Optional[str] = None


class FieldInfo(BaseModel):
    """字段信息"""
    name: str
    type: str
    comment: Optional[str] = None
    is_primary: bool = False


class TableInfo(BaseModel):
    """表信息"""
    name: str
    comment: Optional[str] = None
    fields: List[FieldInfo]
    foreign_keys: Optional[List[Dict[str, str]]] = None


class SchemaInfo(BaseModel):
    """Schema信息"""
    tables: List[TableInfo]
    relationships: Optional[List[Dict[str, Any]]] = None


class DataSourceConfig(BaseModel):
    """数据源配置"""
    db_type: str = Field(..., description="数据库类型: mysql, postgresql, oracle, sqlserver等")
    host: str
    port: int
    database: str
    username: str
    password: str
    db_schema: Optional[str] = Field(None, alias="schema")


class Terminology(BaseModel):
    """术语"""
    word: str
    description: str


class TrainingExample(BaseModel):
    """训练示例"""
    question: str
    sql: str
    description: Optional[str] = None


class PermissionRules(BaseModel):
    """权限规则"""
    row_filters: Optional[List[Dict[str, str]]] = None
    column_permissions: Optional[Dict[str, Dict[str, List[str]]]] = None


class ChatMessage(BaseModel):
    """聊天消息"""
    role: str  # user, assistant
    content: str


class Text2SqlRequest(BaseModel):
    """
    Text2SQL分析请求
    
    包含算法执行所需的全部数据，由后端准备并传递
    """
    query: str = Field(..., description="用户问题")
    datasource_config: DataSourceConfig = Field(..., description="数据源连接配置")
    schema_info: SchemaInfo = Field(..., description="表结构信息")
    terminologies: Optional[List[Terminology]] = Field(None, description="术语列表(RAG增强)")
    training_examples: Optional[List[TrainingExample]] = Field(None, description="训练示例(Few-shot)")
    permission_rules: Optional[PermissionRules] = Field(None, description="权限规则")
    chat_history: Optional[List[ChatMessage]] = Field(None, description="对话历史")
    user_id: Optional[int] = Field(None, description="用户ID(用于日志)")
    datasource_id: Optional[int] = Field(None, description="数据源ID(用于日志)")


class Text2SqlResponse(BaseModel):
    """Text2SQL完整响应(非流式)"""
    sql: Optional[str] = None
    filtered_sql: Optional[str] = None
    execution_result: Optional[Dict[str, Any]] = None
    chart_config: Optional[Dict[str, Any]] = None
    render_data: Optional[Dict[str, Any]] = None
    summary: Optional[str] = None
    recommendations: List[str] = Field(default_factory=list)
    success: bool = True
    error: Optional[str] = None
