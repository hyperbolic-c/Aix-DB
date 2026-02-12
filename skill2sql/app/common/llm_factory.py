"""LLM 工厂：根据请求配置构造模型客户端。"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

DEFAULT_TEMPERATURE = 0.7


def _coerce_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def create_llm(config: Dict[str, Any], default_timeout: int) -> Any:
    """
    创建 LLM 客户端。

    Args:
        config: LLM 配置字典
        default_timeout: 默认超时时间（秒）
    """
    if config is None:
        raise ValueError("缺少 llm 配置")

    provider = (config.get("provider") or "openai").lower()
    model = config.get("model")
    if not model:
        raise ValueError("llm.model 不能为空")

    base_url = config.get("base_url")
    api_key = config.get("api_key")
    temperature = _coerce_float(config.get("temperature"), DEFAULT_TEMPERATURE)
    timeout = _coerce_int(config.get("timeout"), default_timeout)

    def _get_openai():
        try:
            from langchain_openai import ChatOpenAI
        except Exception as e:
            logger.error(
                "Failed to import ChatOpenAI, check langchain-openai installation: %s",
                e,
            )
            raise

        return ChatOpenAI(
            model=model,
            temperature=temperature,
            base_url=base_url,
            api_key=api_key or "empty",
            timeout=timeout,
        )

    def _get_ollama():
        try:
            from langchain_ollama import ChatOllama
        except Exception as e:
            logger.warning("Failed to import ChatOllama, fallback to ChatOpenAI: %s", e)
            return _get_openai()

        return ChatOllama(
            model=model,
            temperature=temperature,
            base_url=base_url,
            timeout=timeout,
        )

    if provider == "ollama":
        return _get_ollama()

    return _get_openai()
