"""请求体定义。"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DatasourceConfig(BaseModel):
    type: str = Field(..., description="数据源类型")
    uri: Optional[str] = Field(None, description="SQLAlchemy URI")
    db_schema: Optional[str] = Field(None, description="Schema")
    config: Optional[Dict[str, Any]] = Field(
        default=None, description="用于生成 URI 的配置"
    )


class LLMConfig(BaseModel):
    provider: str = Field("openai", description="模型提供方")
    model: str = Field(..., description="模型名称")
    base_url: Optional[str] = Field(None, description="API Base URL")
    api_key: Optional[str] = Field(None, description="API Key")
    temperature: Optional[float] = Field(0.7, description="采样温度")
    timeout: Optional[int] = Field(None, description="超时时间（秒）")


class ReportOptions(BaseModel):
    recursion_limit: Optional[int] = Field(None, description="最大递归层数")
    task_timeout: Optional[int] = Field(None, description="总任务超时")
    stream_idle_timeout: Optional[int] = Field(None, description="SSE 空闲超时")
    max_messages: Optional[int] = Field(None, description="最大消息数")


class ReportRunRequest(BaseModel):
    query: str
    chat_id: Optional[str] = None
    uuid: Optional[str] = None
    datasource: DatasourceConfig
    llm: LLMConfig
    skills: Optional[List[str]] = None
    options: Optional[ReportOptions] = None


class ReportStopRequest(BaseModel):
    task_id: str
