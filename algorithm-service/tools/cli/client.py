"""
HTTP客户端模块
处理与算法服务的通信，支持SSE流式响应
"""

import json
import logging
import requests
from typing import Dict, Any, Iterator, Optional, Callable, List
from urllib.parse import urljoin

from .config import Config

logger = logging.getLogger(__name__)


class AlgorithmClient:
    """
    算法服务HTTP客户端
    
    支持发送Text2SQL请求并接收SSE流式响应
    """
    
    def __init__(self, config: Optional[Config] = None):
        """
        初始化客户端
        
        Args:
            config: 配置对象，如果为None则使用默认配置
        """
        self.config = config or Config()
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        })
    
    def _build_request_body(
        self,
        question: str,
        custom_schema: Optional[Dict] = None,
        custom_datasource: Optional[Dict] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        构建请求体
        
        Args:
            question: 用户问题
            custom_schema: 自定义Schema，如果为None则使用默认
            custom_datasource: 自定义数据源配置，如果为None则使用默认
            chat_history: 对话历史记录
            
        Returns:
            请求体字典
        """
        # 构建Schema信息
        if custom_schema:
            schema_info = custom_schema
        else:
            # 从文件加载默认Schema
            schema_info = self._load_default_schema()
        
        # 构建数据源配置
        if custom_datasource:
            datasource_config = custom_datasource
        else:
            # SQLite只需要db_type和db_path
            datasource_config = {
                "db_type": self.config.db_type,
                "db_path": self.config.db_path,
                # 添加必需的字段（对于SQLite这些不会被使用）
                "host": "localhost",
                "port": 0,
                "database": "final",
                "username": "",
                "password": "",
            }
        
        body = {
            "query": question,
            "datasource_config": datasource_config,
            "schema_info": schema_info,
            "terminologies": [],
            "training_examples": [],
            "permission_rules": None,
            "user_id": 1,
        }
        
        # 添加对话历史
        if chat_history:
            body["chat_history"] = chat_history
        
        return body
    
    def _load_default_schema(self) -> Dict[str, Any]:
        """加载默认Schema"""
        import os
        from pathlib import Path
        
        # 尝试从多个位置加载Schema
        possible_paths = [
            Path(self.config.db_path).parent.parent / "finalTableSchema.xlsx",
            Path(__file__).parent.parent.parent / "data" / "schema_from_excel.json",
            Path(__file__).parent.parent.parent / "data" / "schema.json",
        ]
        
        for path in possible_paths:
            if path.exists():
                if path.suffix == ".json":
                    with open(path, 'r', encoding='utf-8') as f:
                        return json.load(f)
                elif path.suffix == ".xlsx":
                    # 从Excel解析Schema
                    return self._parse_excel_schema(str(path))
        
        # 如果都找不到，返回最小化Schema
        logger.warning("无法加载Schema文件，使用最小化Schema")
        return {
            "database": "final",
            "db_type": "sqlite",
            "tables": []
        }
    
    def _parse_excel_schema(self, excel_path: str) -> Dict[str, Any]:
        """从Excel解析Schema"""
        try:
            import pandas as pd
            
            df = pd.read_excel(excel_path)
            schema = {
                "database": "final",
                "db_type": "sqlite",
                "tables": []
            }
            
            current_table = None
            for _, row in df.iterrows():
                if pd.notna(row['序号']):
                    if current_table:
                        schema["tables"].append(current_table)
                    current_table = {
                        "name": row['表名'],
                        "comment": row['表描述'] if pd.notna(row['表描述']) else "",
                        "fields": []
                    }
                
                if current_table and pd.notna(row['字段名']):
                    field = {
                        "name": row['字段名'],
                        "type": row['字段类型'] if pd.notna(row['字段类型']) else "TEXT",
                        "comment": row['字段描述'] if pd.notna(row['字段描述']) else ""
                    }
                    current_table["fields"].append(field)
            
            if current_table:
                schema["tables"].append(current_table)
            
            return schema
        except Exception as e:
            logger.error(f"解析Excel Schema失败: {e}")
            return {"database": "final", "db_type": "sqlite", "tables": []}
    
    def analyze(
        self,
        question: str,
        custom_schema: Optional[Dict] = None,
        custom_datasource: Optional[Dict] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
        on_event: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Iterator[Dict[str, Any]]:
        """
        发送分析请求并接收流式响应
        
        Args:
            question: 用户问题
            custom_schema: 自定义Schema
            custom_datasource: 自定义数据源配置
            chat_history: 对话历史记录
            on_event: 事件回调函数，每收到一个事件调用一次
            
        Yields:
            事件字典
        """
        # 确保host以/结尾，这样urljoin才能正确拼接
        host = self.config.host
        if not host.endswith('/'):
            host += '/'
        url = urljoin(host, "analyze")
        body = self._build_request_body(question, custom_schema, custom_datasource, chat_history)
        
        if self.config.debug:
            logger.debug(f"请求URL: {url}")
            logger.debug(f"请求体: {json.dumps(body, ensure_ascii=False, indent=2)}")
        
        try:
            response = self.session.post(
                url,
                json=body,
                stream=True,
                timeout=self.config.timeout,
            )
            response.raise_for_status()
            
            # 解析SSE流
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                
                # SSE格式: data: {json}
                if line.startswith("data: "):
                    data_str = line[6:]  # 去掉 "data: " 前缀
                    
                    try:
                        event = json.loads(data_str)
                        
                        if on_event:
                            on_event(event)
                        
                        yield event
                        
                        # 如果是完成或错误事件，结束流
                        if event.get("event_type") in ["complete", "error"]:
                            break
                            
                    except json.JSONDecodeError as e:
                        logger.warning(f"解析JSON失败: {e}, 数据: {data_str[:100]}")
                        continue
        
        except requests.exceptions.ConnectionError as e:
            error_event = {
                "event_type": "error",
                "message": f"连接失败: 无法连接到算法服务 {self.config.host}",
                "data": {"error_type": "connection_error", "detail": str(e)}
            }
            if on_event:
                on_event(error_event)
            yield error_event
            
        except requests.exceptions.Timeout as e:
            error_event = {
                "event_type": "error",
                "message": f"请求超时: 算法服务响应超过 {self.config.timeout} 秒",
                "data": {"error_type": "timeout_error", "detail": str(e)}
            }
            if on_event:
                on_event(error_event)
            yield error_event
            
        except requests.exceptions.RequestException as e:
            error_event = {
                "event_type": "error",
                "message": f"请求错误: {str(e)}",
                "data": {"error_type": "request_error", "detail": str(e)}
            }
            if on_event:
                on_event(error_event)
            yield error_event
    
    def health_check(self) -> Dict[str, Any]:
        """
        健康检查
        
        Returns:
            健康状态字典
        """
        # 确保host以/结尾，这样urljoin才能正确拼接
        host = self.config.host
        if not host.endswith('/'):
            host += '/'
        url = urljoin(host, "health")
        try:
            response = self.session.get(url, timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    
    def close(self):
        """关闭客户端"""
        self.session.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
