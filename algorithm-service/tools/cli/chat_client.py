"""
聊天服务客户端
用于CLI调用后端服务的聊天API
"""

import json
import logging
from typing import Optional, List, Dict, Any, Iterator
from urllib.parse import urljoin

import requests

from .config import Config

logger = logging.getLogger(__name__)


class ChatClient:
    """
    聊天服务客户端
    调用后端服务的聊天API
    """
    
    def __init__(self, config: Optional[Config] = None):
        """
        初始化客户端
        
        Args:
            config: 配置对象
        """
        self.config = config or Config()
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })
        
        # 当前会话ID
        self.current_session_id: Optional[int] = None
    
    def _get_base_url(self) -> str:
        """获取基础URL"""
        host = self.config.host
        if not host.endswith('/'):
            host += '/'
        return host
    
    def create_session(self, title: Optional[str] = None) -> Dict[str, Any]:
        """
        创建新会话
        
        Args:
            title: 会话标题
            
        Returns:
            会话信息
        """
        url = urljoin(self._get_base_url(), "chat/sessions")
        body = {"title": title} if title else {}
        
        try:
            response = self.session.post(url, json=body, timeout=10)
            response.raise_for_status()
            session = response.json()
            self.current_session_id = session.get("id")
            return session
        except Exception as e:
            logger.error(f"创建会话失败: {e}")
            raise
    
    def list_sessions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        列出所有会话
        
        Args:
            limit: 返回的最大数量
            
        Returns:
            会话列表
        """
        url = urljoin(self._get_base_url(), f"chat/sessions?limit={limit}")
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"获取会话列表失败: {e}")
            return []
    
    def get_session(self, session_id: int) -> Optional[Dict[str, Any]]:
        """
        获取会话详情
        
        Args:
            session_id: 会话ID
            
        Returns:
            会话信息
        """
        url = urljoin(self._get_base_url(), f"chat/sessions/{session_id}")
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"获取会话失败: {e}")
            return None
    
    def delete_session(self, session_id: int) -> bool:
        """
        删除会话
        
        Args:
            session_id: 会话ID
            
        Returns:
            是否成功
        """
        url = urljoin(self._get_base_url(), f"chat/sessions/{session_id}")
        
        try:
            response = self.session.delete(url, timeout=10)
            response.raise_for_status()
            if self.current_session_id == session_id:
                self.current_session_id = None
            return True
        except Exception as e:
            logger.error(f"删除会话失败: {e}")
            return False
    
    def send_message(
        self,
        question: str,
        session_id: Optional[int] = None
    ) -> Iterator[Dict[str, Any]]:
        """
        发送消息（流式返回）
        
        Args:
            question: 用户问题
            session_id: 会话ID，如果为None使用当前会话
            
        Yields:
            事件字典
        """
        if session_id is None:
            session_id = self.current_session_id
        
        if session_id is None:
            # 自动创建新会话
            session = self.create_session()
            session_id = session["id"]
        
        url = urljoin(self._get_base_url(), f"chat/sessions/{session_id}/message")
        body = {"question": question}
        
        try:
            response = self.session.post(
                url,
                json=body,
                stream=True,
                timeout=self.config.timeout,
                headers={"Accept": "text/event-stream"}
            )
            response.raise_for_status()
            
            # 解析SSE流
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                
                if line.startswith("data: "):
                    data_str = line[6:]
                    try:
                        event = json.loads(data_str)
                        yield event
                        
                        if event.get("event_type") in ["complete", "error"]:
                            break
                    except json.JSONDecodeError:
                        continue
        
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            yield {
                "event_type": "error",
                "message": f"发送消息失败: {str(e)}",
                "data": {"error_type": "request_error"}
            }
    
    def get_history(
        self,
        session_id: Optional[int] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        获取会话历史
        
        Args:
            session_id: 会话ID
            limit: 返回的最大消息数
            
        Returns:
            消息列表
        """
        if session_id is None:
            session_id = self.current_session_id
        
        if session_id is None:
            return []
        
        url = urljoin(
            self._get_base_url(),
            f"chat/sessions/{session_id}/history?limit={limit}"
        )
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get("messages", [])
        except Exception as e:
            logger.error(f"获取历史失败: {e}")
            return []
    
    def clear_history(self, session_id: Optional[int] = None) -> bool:
        """
        清空会话历史
        
        Args:
            session_id: 会话ID
            
        Returns:
            是否成功
        """
        if session_id is None:
            session_id = self.current_session_id
        
        if session_id is None:
            return False
        
        url = urljoin(self._get_base_url(), f"chat/sessions/{session_id}/clear")
        
        try:
            response = self.session.post(url, timeout=10)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"清空历史失败: {e}")
            return False
    
    def rename_session(self, session_id: int, title: str) -> bool:
        """
        重命名会话
        
        Args:
            session_id: 会话ID
            title: 新标题
            
        Returns:
            是否成功
        """
        url = urljoin(
            self._get_base_url(),
            f"chat/sessions/{session_id}/rename?title={title}"
        )
        
        try:
            response = self.session.post(url, timeout=10)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"重命名会话失败: {e}")
            return False
    
    def switch_session(self, session_id: int) -> bool:
        """
        切换到指定会话
        
        Args:
            session_id: 会话ID
            
        Returns:
            是否成功
        """
        session = self.get_session(session_id)
        if session:
            self.current_session_id = session_id
            return True
        return False
    
    def health_check(self) -> Dict[str, Any]:
        """
        健康检查
        
        Returns:
            健康状态
        """
        url = urljoin(self._get_base_url(), "chat/health")
        
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
