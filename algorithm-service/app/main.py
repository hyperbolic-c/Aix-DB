"""
算法服务主入口
FastAPI应用
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.chat_service.router import router as chat_router

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="Aix-DB Algorithm Service",
    description="Text2SQL算法服务 - 提供自然语言转SQL分析能力",
    version="1.0.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境需要限制
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")


@app.on_event("startup")
async def startup_event():
    """服务启动事件"""
    logger.info("算法服务启动中...")
    # 这里可以初始化模型、加载配置等
    logger.info("算法服务启动完成")


@app.on_event("shutdown")
async def shutdown_event():
    """服务关闭事件"""
    logger.info("算法服务关闭中...")
    # 这里可以清理资源
    logger.info("算法服务关闭完成")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
