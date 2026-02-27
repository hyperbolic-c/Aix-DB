"""
Text2SQL Service 客户端
主应用调用 Text2SQL 算法的客户端
组装完整信息传入算法服务
"""

import httpx
from typing import List, Dict, Optional, Any
from dataclasses import dataclass


@dataclass
class LLMConfig:
    """LLM 配置"""
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    api_key: str = ""
    base_url: Optional[str] = None
    temperature: float = 0.7
    timeout: int = 60


@dataclass
class TableSchema:
    """表结构"""
    name: str
    columns: List[Dict]
    comment: Optional[str] = None


@dataclass
class TableRelation:
    """表关系"""
    from_table: str
    from_column: str
    to_table: str
    to_column: str


@dataclass
class ChatMessage:
    """聊天消息"""
    role: str
    content: str
    sql: Optional[str] = None
    timestamp: Optional[str] = None


class Text2SQLServiceClient:
    """Text2SQL 服务客户端 - 完整信息组装
    
    主应用使用此客户端调用 Text2SQL 算法服务，
    客户端负责组装原实现中 SQL 生成所需的全部信息。
    """
    
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        """
        Args:
            base_url: Text2SQL 服务地址，如 http://localhost:8080
            api_key: API Key（可选）
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=60)
    
    async def generate_sql(
        self,
        query: str,
        tables: List[Dict],
        db_type: str,
        db_name: Optional[str] = None,
        table_relations: Optional[List[Dict]] = None,
        llm_config: Optional[LLMConfig] = None,
        chat_history: Optional[List[Dict]] = None,
        terminologies: Optional[str] = None,
        training_examples: Optional[str] = None,
        error_message: Optional[str] = None,
        enable_query_limit: bool = True,
        change_title: bool = False,
        lang: str = "简体中文",
        top_k: int = 6
    ) -> Dict[str, Any]:
        """调用 Text2SQL 服务生成 SQL
        
        组装原实现中 SQL 生成所需的全部信息：
        1. Schema 信息（全量表结构）
        2. 数据源配置（类型、数据库名）
        3. 表关系（用于JOIN）
        4. 术语和训练示例（RAG）
        5. LLM 配置
        6. 多轮对话历史
        
        Args:
            query: 用户问题
            tables: 全量表结构列表
            db_type: 数据库类型
            db_name: 数据库名
            table_relations: 表关系列表
            llm_config: LLM 配置
            chat_history: 聊天记录
            terminologies: 术语文本
            training_examples: 训练示例文本
            error_message: 错误信息（用于纠错）
            enable_query_limit: 是否启用数据量限制
            change_title: 是否生成对话标题
            lang: 输出语言
            top_k: Schema 检索返回表数
            
        Returns:
            生成结果字典
        """
        # 组装请求
        payload = {
            "query": query,
            "tables": tables,
            "db_type": db_type,
            "db_name": db_name,
            "table_relations": table_relations or [],
            "llm": self._build_llm_config(llm_config),
            "chat_history": chat_history or [],
            "terminologies": terminologies or "",
            "training_examples": training_examples or "",
            "error_message": error_message or "",
            "enable_query_limit": enable_query_limit,
            "change_title": change_title,
            "lang": lang,
            "top_k": top_k
        }
        
        # 调用服务
        headers = {}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
            
        response = await self.client.post(
            f"{self.base_url}/api/v1/sql/generate",
            json=payload,
            headers=headers
        )
        response.raise_for_status()
        return response.json()
    
    def _build_llm_config(self, config: Optional[LLMConfig]) -> Dict:
        """构建 LLM 配置"""
        if config is None:
            # 默认配置
            return {
                "provider": "openai",
                "model": "gpt-4o-mini",
                "api_key": "",
                "temperature": 0.7,
                "timeout": 60
            }
        
        return {
            "provider": config.provider,
            "model": config.model,
            "api_key": config.api_key,
            "base_url": config.base_url,
            "temperature": config.temperature,
            "timeout": config.timeout
        }
    
    async def close(self):
        """关闭客户端"""
        await self.client.aclose()
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()


class Text2SQLServiceClientSync:
    """Text2SQL 服务客户端 - 同步版本"""
    
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.client = httpx.Client(timeout=60)
    
    def generate_sql(
        self,
        query: str,
        tables: List[Dict],
        db_type: str,
        db_name: Optional[str] = None,
        table_relations: Optional[List[Dict]] = None,
        llm_config: Optional[LLMConfig] = None,
        chat_history: Optional[List[Dict]] = None,
        terminologies: Optional[str] = None,
        training_examples: Optional[str] = None,
        error_message: Optional[str] = None,
        enable_query_limit: bool = True,
        change_title: bool = False,
        lang: str = "简体中文",
        top_k: int = 6
    ) -> Dict[str, Any]:
        """同步调用 Text2SQL 服务生成 SQL"""
        payload = {
            "query": query,
            "tables": tables,
            "db_type": db_type,
            "db_name": db_name,
            "table_relations": table_relations or [],
            "llm": self._build_llm_config(llm_config),
            "chat_history": chat_history or [],
            "terminologies": terminologies or "",
            "training_examples": training_examples or "",
            "error_message": error_message or "",
            "enable_query_limit": enable_query_limit,
            "change_title": change_title,
            "lang": lang,
            "top_k": top_k
        }
        
        headers = {}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
            
        response = self.client.post(
            f"{self.base_url}/api/v1/sql/generate",
            json=payload,
            headers=headers
        )
        response.raise_for_status()
        return response.json()
    
    def _build_llm_config(self, config: Optional[LLMConfig]) -> Dict:
        """构建 LLM 配置"""
        if config is None:
            return {
                "provider": "openai",
                "model": "gpt-4o-mini",
                "api_key": "",
                "temperature": 0.7,
                "timeout": 60
            }
        
        return {
            "provider": config.provider,
            "model": config.model,
            "api_key": config.api_key,
            "base_url": config.base_url,
            "temperature": config.temperature,
            "timeout": config.timeout
        }
    
    def close(self):
        """关闭客户端"""
        self.client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
