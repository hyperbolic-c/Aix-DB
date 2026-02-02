"""
聊天服务API路由
提供多轮对话的REST API和SSE流式接口
"""

import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, Path
from fastapi.responses import StreamingResponse

from .service import ChatService
from .models import (
    CreateSessionRequest,
    SendMessageRequest,
    SessionResponse,
    HistoryResponse,
    ChatSession,
    ChatMessage
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# 创建服务实例
chat_service = ChatService()


@router.post("/sessions", response_model=SessionResponse)
async def create_session(request: CreateSessionRequest):
    """
    创建新会话
    
    Args:
        request: 创建会话请求
        
    Returns:
        创建的会话信息
    """
    session = chat_service.create_session(request.title)
    return SessionResponse(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        message_count=0
    )


@router.get("/sessions")
async def list_sessions(limit: int = 20):
    """
    列出所有会话
    
    Args:
        limit: 返回的最大数量
        
    Returns:
        会话列表
    """
    sessions = chat_service.list_sessions(limit)
    return [
        SessionResponse(
            id=s.id,
            title=s.title,
            created_at=s.created_at,
            updated_at=s.updated_at,
            message_count=s.message_count
        )
        for s in sessions
    ]


@router.get("/sessions/{session_id}")
async def get_session(session_id: int = Path(..., description="会话ID")):
    """
    获取会话详情
    
    Args:
        session_id: 会话ID
        
    Returns:
        会话详情
    """
    session = chat_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    return SessionResponse(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        message_count=session.message_count
    )


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: int = Path(..., description="会话ID")):
    """
    删除会话
    
    Args:
        session_id: 会话ID
    """
    session = chat_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    chat_service.delete_session(session_id)
    return {"success": True, "message": f"会话 {session_id} 已删除"}


@router.post("/sessions/{session_id}/message")
async def send_message(
    session_id: int = Path(..., description="会话ID"),
    request: SendMessageRequest = None
):
    """
    发送消息（流式返回）
    
    调用算法服务进行Text2SQL分析，并流式返回处理过程和结果
    
    Args:
        session_id: 会话ID
        request: 发送消息请求
        
    Returns:
        SSE流式响应
    """
    # 检查会话是否存在
    session = chat_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    question = request.question if request else ""
    if not question:
        raise HTTPException(status_code=400, detail="问题不能为空")
    
    logger.info(f"会话 {session_id}: 接收问题 - {question}")
    
    async def event_generator() -> AsyncGenerator[str, None]:
        """生成SSE事件流"""
        try:
            async for event in chat_service.send_message(session_id, question):
                # 格式化为SSE格式
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"流式处理出错: {e}")
            error_event = {
                "event_type": "error",
                "message": f"处理失败: {str(e)}",
                "data": {"error_type": "stream_error"}
            }
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.get("/sessions/{session_id}/history")
async def get_history(
    session_id: int = Path(..., description="会话ID"),
    limit: int = 20
):
    """
    获取会话历史
    
    Args:
        session_id: 会话ID
        limit: 返回的最大消息数
        
    Returns:
        历史消息列表
    """
    session = chat_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    messages = chat_service.get_history(session_id, limit)
    return HistoryResponse(
        session_id=session_id,
        messages=messages
    )


@router.post("/sessions/{session_id}/clear")
async def clear_history(session_id: int = Path(..., description="会话ID")):
    """
    清空会话历史
    
    Args:
        session_id: 会话ID
    """
    session = chat_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    chat_service.clear_history(session_id)
    return {"success": True, "message": f"会话 {session_id} 的历史已清空"}


@router.post("/sessions/{session_id}/rename")
async def rename_session(
    session_id: int = Path(..., description="会话ID"),
    title: str = ""
):
    """
    重命名会话
    
    Args:
        session_id: 会话ID
        title: 新标题
    """
    session = chat_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    if not title:
        raise HTTPException(status_code=400, detail="标题不能为空")
    
    chat_service.rename_session(session_id, title)
    return {"success": True, "message": f"会话已重命名为: {title}"}


@router.get("/health")
async def health_check():
    """
    健康检查
    
    Returns:
        健康状态
    """
    health = await chat_service.health_check()
    return health
