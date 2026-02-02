"""
SQL示例模型
用于存储自然语言到SQL的示例
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class SQLExample(BaseModel):
    """SQL示例模型"""
    id: Optional[int] = None
    question: str = Field(..., description="自然语言问题")
    sql: str = Field(..., description="SQL语句")
    explanation: Optional[str] = Field(None, description="解释说明")
    datasource_type: Optional[str] = Field(None, description="数据源类型")
    datasource_id: Optional[int] = Field(None, description="关联的数据源ID")
    oid: int = Field(default=1, description="组织ID")
    vector_version: int = Field(default=0, description="向量版本号，用于同步追踪")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    def to_vector_text(self) -> str:
        """转换为用于向量化的文本"""
        return self.question
    
    def to_vector_metadata(self) -> dict:
        """转换为向量库存储的元数据"""
        return {
            "id": self.id,
            "sql": self.sql,
            "explanation": self.explanation,
            "datasource_type": self.datasource_type,
            "datasource_id": self.datasource_id,
            "oid": self.oid
        }


class SQLExampleCreate(BaseModel):
    """创建SQL示例请求"""
    question: str = Field(..., description="自然语言问题")
    sql: str = Field(..., description="SQL语句")
    explanation: Optional[str] = Field(None, description="解释说明")
    datasource_type: Optional[str] = Field(None, description="数据源类型")
    datasource_id: Optional[int] = Field(None, description="关联的数据源ID")


class SQLExampleUpdate(BaseModel):
    """更新SQL示例请求"""
    question: Optional[str] = None
    sql: Optional[str] = None
    explanation: Optional[str] = None
