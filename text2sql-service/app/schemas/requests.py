"""
Text2SQL Service - 请求/响应模型
完整信息传入方案 - 所有数据通过 API 传入，服务不连接数据库
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ColumnSchema(BaseModel):
    """字段结构"""
    name: str = Field(..., description="字段名")
    type: str = Field(..., description="字段类型")
    comment: Optional[str] = Field(None, description="字段注释")
    is_primary: bool = Field(False, description="是否主键")


class TableSchema(BaseModel):
    """表结构"""
    name: str = Field(..., description="表名")
    comment: Optional[str] = Field(None, description="表注释")
    columns: List[ColumnSchema] = Field(..., description="字段列表")


class TableRelation(BaseModel):
    """表关系"""
    from_table: str = Field(..., description="源表")
    from_column: str = Field(..., description="源字段")
    to_table: str = Field(..., description="目标表")
    to_column: str = Field(..., description="目标字段")


class ChatMessage(BaseModel):
    """聊天消息"""
    role: str = Field(..., description="user / assistant")
    content: str = Field(..., description="消息内容")
    sql: Optional[str] = Field(None, description="SQL（assistant消息）")
    timestamp: Optional[str] = Field(None, description="时间戳")


class LLMConfig(BaseModel):
    """LLM 配置"""
    provider: str = Field("openai", description="openai/azure/ollama")
    model: str = Field(..., description="模型名")
    api_key: str = Field(..., description="API Key")
    base_url: Optional[str] = Field(None, description="自定义 base_url")
    temperature: float = Field(0.7, description="温度参数")
    timeout: int = Field(60, description="超时时间（秒）")


class SQLGenerateRequest(BaseModel):
    """SQL 生成请求 - 完整信息传入
    
    所有原实现中 SQL 生成所需的信息都通过此请求传入，
    算法服务不连接数据库，纯算法逻辑。
    """
    
    # ========== 核心信息 ==========
    query: str = Field(..., description="用户当前问题（必填）")
    
    # ========== Schema 信息（全量传入） ==========
    tables: List[TableSchema] = Field(..., description="所有表结构（必填）")
    db_type: str = Field(..., description="数据库类型：mysql/pg/oracle/...")
    db_name: Optional[str] = Field(None, description="数据库名/Schema名")
    
    # ========== 表关系（可选，用于JOIN生成） ==========
    table_relations: Optional[List[TableRelation]] = Field(None, description="表关系列表")
    
    # ========== LLM 配置 ==========
    llm: LLMConfig = Field(..., description="LLM 配置（必填）")
    
    # ========== 多轮对话 ==========
    chat_history: Optional[List[ChatMessage]] = Field(None, description="聊天记录")
    
    # ========== RAG 增强（可选） ==========
    terminologies: Optional[str] = Field(None, description="术语定义文本")
    training_examples: Optional[str] = Field(None, description="训练示例文本")
    old_questions: Optional[List[str]] = Field(None, description="历史问题列表（用于推荐）")
    
    # ========== 纠错重试 ==========
    previous_sql: Optional[str] = Field(None, description="上次生成的SQL")
    error_message: Optional[str] = Field(None, description="错误信息")
    
    # ========== 生成选项 ==========
    top_k: int = Field(6, description="Schema检索返回表数")
    enable_query_limit: bool = Field(True, description="是否启用数据量限制")
    change_title: bool = Field(False, description="是否生成对话标题")
    lang: str = Field("简体中文", description="输出语言")


class SQLGenerateResponse(BaseModel):
    """SQL 生成响应"""
    
    # ========== 核心结果 ==========
    success: bool = Field(..., description="是否成功")
    sql: Optional[str] = Field(None, description="生成的 SQL")
    chart_type: Optional[str] = Field(None, description="图表类型：table/line/bar/pie/column")
    used_tables: List[str] = Field(default_factory=list, description="SQL中使用的表名")
    
    # ========== 对话标题 ==========
    brief: Optional[str] = Field(None, description="对话标题（change_title=True时）")
    
    # ========== 调试信息 ==========
    retrieved_tables: List[str] = Field(default_factory=list, description="BM25检索到的表")
    tokens: List[str] = Field(default_factory=list, description="分词结果")
    
    # ========== 错误信息 ==========
    message: Optional[str] = Field(None, description="错误描述")


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = Field(..., description="服务状态")
    version: str = Field(..., description="版本号")
