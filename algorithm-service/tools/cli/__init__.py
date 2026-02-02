"""
算法服务CLI调试工具

提供交互式终端，用于调试算法服务的Text2SQL功能
"""

from .client import AlgorithmClient
from .renderer import EventRenderer
from .config import Config
from .interactive import InteractiveCLI

__version__ = "1.0.0"
__all__ = ["AlgorithmClient", "EventRenderer", "Config", "InteractiveCLI"]
