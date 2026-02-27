"""
服务配置
"""

import os
from typing import Optional


class Settings:
    """服务配置"""
    
    # 服务配置
    PORT: int = int(os.getenv("PORT", 8080))
    HOST: str = os.getenv("HOST", "0.0.0.0")
    
    # API Key（可选）
    API_KEY: Optional[str] = os.getenv("API_KEY")
    
    # 调试模式
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"


settings = Settings()
