"""应用配置。"""

from typing import List, Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    api_key: Optional[str] = None
    cors_allow_origins: List[str] = ["*"]
    cors_allow_methods: List[str] = ["*"]
    cors_allow_headers: List[str] = ["*"]
    sse_retry_ms: int = 15000

    class Config:
        env_prefix = "SKILL2SQL_"


settings = Settings()
