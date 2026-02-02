"""
配置管理模块
"""

import os
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional


@dataclass
class Config:
    """
    CLI配置类
    """
    # 服务配置
    host: str = "http://localhost:8002/api/v1"
    timeout: int = 60
    
    # 默认数据源配置
    db_path: str = "/Users/liam/LLMPro/Aix-DB/target_db/competition/final.db"
    db_type: str = "sqlite"
    
    # 显示配置
    debug: bool = False
    raw_mode: bool = False  # 显示原始JSON
    show_sql: bool = True
    show_summary: bool = True
    show_recommendations: bool = True
    
    # 历史记录
    history_file: Optional[str] = None
    max_history: int = 100
    
    def __post_init__(self):
        if self.history_file is None:
            self.history_file = str(Path.home() / ".algorithm_cli_history.json")
    
    @classmethod
    def from_file(cls, config_path: str) -> "Config":
        """从文件加载配置"""
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls(**data)
    
    def to_file(self, config_path: str):
        """保存配置到文件"""
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(asdict(self), f, ensure_ascii=False, indent=2)
    
    @classmethod
    def from_env(cls) -> "Config":
        """从环境变量加载配置"""
        return cls(
            host=os.getenv("ALGORITHM_HOST", "http://localhost:8002"),
            timeout=int(os.getenv("ALGORITHM_TIMEOUT", "60")),
            db_path=os.getenv("DB_PATH", "/Users/liam/LLMPro/Aix-DB/target_db/competition/final.db"),
            db_type=os.getenv("DB_TYPE", "sqlite"),
            debug=os.getenv("ALGORITHM_DEBUG", "").lower() == "true",
        )


# 默认配置实例
default_config = Config()
