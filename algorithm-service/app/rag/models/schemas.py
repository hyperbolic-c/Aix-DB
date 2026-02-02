"""
RAG 检索结果数据模型
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class SchemaRetrievalResult(BaseModel):
    """Schema检索结果"""
    table_name: str = Field(..., description="表名")
    table_description: Optional[str] = Field(None, description="表描述")
    columns: List[Dict[str, Any]] = Field(default_factory=list, description="字段信息")
    relevance_score: float = Field(..., description="相关性分数")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="额外元数据")
    
    def to_text(self) -> str:
        """转换为文本格式"""
        text = f"表名: {self.table_name}"
        if self.table_description:
            text += f"\n描述: {self.table_description}"
        if self.columns:
            text += "\n字段:"
            for col in self.columns:
                col_name = col.get("name", "")
                col_type = col.get("type", "")
                col_desc = col.get("description", "")
                text += f"\n  - {col_name} ({col_type}): {col_desc}"
        return text


class TerminologyResult(BaseModel):
    """术语检索结果"""
    term: str = Field(..., description="术语")
    definition: str = Field(..., description="定义/解释")
    category: Optional[str] = Field(None, description="分类")
    synonyms: List[str] = Field(default_factory=list, description="同义词")
    relevance_score: float = Field(..., description="相关性分数")
    
    def to_text(self) -> str:
        """转换为文本格式"""
        text = f"术语: {self.term}\n定义: {self.definition}"
        if self.category:
            text += f"\n分类: {self.category}"
        if self.synonyms:
            text += f"\n同义词: {', '.join(self.synonyms)}"
        return text


class SQLExampleResult(BaseModel):
    """SQL示例检索结果"""
    question: str = Field(..., description="自然语言问题")
    sql: str = Field(..., description="SQL语句")
    explanation: Optional[str] = Field(None, description="解释说明")
    datasource_type: Optional[str] = Field(None, description="数据源类型")
    relevance_score: float = Field(..., description="相关性分数")
    
    def to_text(self) -> str:
        """转换为文本格式"""
        text = f"问题: {self.question}\nSQL: {self.sql}"
        if self.explanation:
            text += f"\n解释: {self.explanation}"
        return text


class RetrievalResult(BaseModel):
    """统一检索结果"""
    schemas: List[SchemaRetrievalResult] = Field(default_factory=list, description="Schema检索结果")
    terminologies: List[TerminologyResult] = Field(default_factory=list, description="术语检索结果")
    sql_examples: List[SQLExampleResult] = Field(default_factory=list, description="SQL示例检索结果")
    
    def is_empty(self) -> bool:
        """检查是否为空"""
        return not (self.schemas or self.terminologies or self.sql_examples)
    
    def to_prompt_context(self) -> Dict[str, str]:
        """
        转换为Prompt上下文
        
        Returns:
            包含schema_text、terminology_text、example_text的字典
        """
        schema_text = "\n\n".join([s.to_text() for s in self.schemas]) if self.schemas else ""
        
        terminology_text = "\n\n".join([t.to_text() for t in self.terminologies]) if self.terminologies else ""
        
        example_text = "\n\n".join([e.to_text() for e in self.sql_examples]) if self.sql_examples else ""
        
        return {
            "schema_text": schema_text,
            "terminology_text": terminology_text,
            "example_text": example_text
        }
