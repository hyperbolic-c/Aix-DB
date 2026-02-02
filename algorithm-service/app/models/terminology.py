"""
术语模型
用于存储业务术语和定义
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class Terminology(BaseModel):
    """术语模型"""
    id: Optional[int] = None
    term: str = Field(..., description="术语名称")
    definition: str = Field(..., description="术语定义/解释")
    category: Optional[str] = Field(None, description="分类")
    synonyms: List[str] = Field(default_factory=list, description="同义词列表")
    datasource_id: Optional[int] = Field(None, description="关联的数据源ID")
    oid: int = Field(default=1, description="组织ID")
    vector_version: int = Field(default=0, description="向量版本号，用于同步追踪")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    def to_vector_text(self) -> str:
        """转换为用于向量化的文本"""
        text = f"{self.term}: {self.definition}"
        if self.synonyms:
            text += f" 同义词: {', '.join(self.synonyms)}"
        if self.category:
            text += f" 分类: {self.category}"
        return text
    
    def to_vector_metadata(self) -> dict:
        """转换为向量库存储的元数据"""
        return {
            "id": self.id,
            "term": self.term,
            "category": self.category,
            "datasource_id": self.datasource_id,
            "oid": self.oid
        }


class TerminologyCreate(BaseModel):
    """创建术语请求"""
    term: str = Field(..., description="术语名称")
    definition: str = Field(..., description="术语定义/解释")
    category: Optional[str] = Field(None, description="分类")
    synonyms: List[str] = Field(default_factory=list, description="同义词列表")
    datasource_id: Optional[int] = Field(None, description="关联的数据源ID")


class TerminologyUpdate(BaseModel):
    """更新术语请求"""
    term: Optional[str] = None
    definition: Optional[str] = None
    category: Optional[str] = None
    synonyms: Optional[List[str]] = None
