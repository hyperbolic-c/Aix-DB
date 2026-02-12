"""响应相关枚举与模型。"""

from enum import Enum
from typing import Any, Dict

from pydantic import BaseModel


class DataTypeEnum(Enum):
    ANSWER = ("t02", "答案")
    LOCATION = ("t03", "溯源")
    BUS_DATA = ("t04", "业务数据")
    TASK_ID = ("t11", "任务ID")
    RECORD_ID = ("t12", "记录ID")
    STEP_PROGRESS = ("t14", "步骤进度信息")
    STREAM_END = ("t99", "流式推流结束")


class HealthResponse(BaseModel):
    status: str


class ErrorResponse(BaseModel):
    detail: Any


def sse_payload(content: str, message_type: str, data_type: str) -> Dict[str, Any]:
    return {
        "data": {"messageType": message_type, "content": content},
        "dataType": data_type,
    }
