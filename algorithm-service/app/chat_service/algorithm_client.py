"""
算法服务客户端
用于后端服务调用算法服务的Text2SQL接口
"""

import json
import logging
import httpx
from typing import AsyncGenerator, Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class AlgorithmClient:
    """
    算法服务HTTP客户端
    用于后端服务调用算法服务的SSE接口
    """
    
    def __init__(self, base_url: str = "http://localhost:8002/api/v1"):
        """
        初始化客户端
        
        Args:
            base_url: 算法服务基础URL
        """
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=60.0)
    
    async def analyze(
        self,
        question: str,
        schema_info: Dict[str, Any],
        datasource_config: Dict[str, Any],
        chat_history: Optional[List[Dict[str, str]]] = None,
        terminologies: Optional[List[Dict[str, str]]] = None,
        training_examples: Optional[List[Dict[str, str]]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        调用算法服务的分析接口
        
        Args:
            question: 用户问题
            schema_info: Schema信息
            datasource_config: 数据源配置
            chat_history: 对话历史
            terminologies: 术语列表
            training_examples: 训练示例列表
            
        Yields:
            事件字典
        """
        url = f"{self.base_url}/analyze"
        
        body = {
            "query": question,
            "datasource_config": datasource_config,
            "schema_info": schema_info,
            "terminologies": terminologies if terminologies else [],
            "training_examples": training_examples if training_examples else [],
            "permission_rules": None,
            "user_id": 1,
        }
        
        if chat_history:
            body["chat_history"] = chat_history
        
        try:
            async with self.client.stream(
                "POST",
                url,
                json=body,
                headers={"Accept": "text/event-stream"}
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    
                    # SSE格式: data: {json}
                    if line.startswith("data: "):
                        data_str = line[6:]
                        
                        try:
                            event = json.loads(data_str)
                            yield event
                            
                            # 如果是完成或错误事件，结束流
                            if event.get("event_type") in ["complete", "error"]:
                                break
                                
                        except json.JSONDecodeError as e:
                            logger.warning(f"解析JSON失败: {e}")
                            continue
        
        except httpx.HTTPError as e:
            logger.error(f"HTTP错误: {e}")
            yield {
                "event_type": "error",
                "message": f"算法服务调用失败: {str(e)}",
                "data": {"error_type": "http_error"}
            }
        except Exception as e:
            logger.error(f"未知错误: {e}")
            yield {
                "event_type": "error",
                "message": f"未知错误: {str(e)}",
                "data": {"error_type": "unknown_error"}
            }
    
    async def health_check(self) -> Dict[str, Any]:
        """
        健康检查
        
        Returns:
            健康状态字典
        """
        try:
            response = await self.client.get(f"{self.base_url}/health", timeout=5.0)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    
    async def close(self):
        """关闭客户端"""
        await self.client.aclose()
