"""SSE 辅助工具。"""

import asyncio
import json
import logging
from typing import AsyncGenerator, Optional

from starlette.requests import Request

from ..schemas.responses import DataTypeEnum, sse_payload

logger = logging.getLogger(__name__)


class SSEWriter:
    def __init__(self):
        self.queue: asyncio.Queue = asyncio.Queue()
        self.closed = False

    async def write(self, data: str):
        if self.closed:
            return
        await self.queue.put(data)

    async def flush(self):
        return None

    async def close(self):
        if not self.closed:
            self.closed = True
            await self.queue.put(None)


def format_sse_message(
    content: str,
    message_type: str = "continue",
    data_type: str = DataTypeEnum.ANSWER.value[0],
) -> str:
    payload = sse_payload(content, message_type, data_type)
    return "data:" + json.dumps(payload, ensure_ascii=False) + "\n\n"


async def sse_event_stream(
    request: Request,
    writer: SSEWriter,
    task: asyncio.Task,
    retry_ms: Optional[int] = None,
) -> AsyncGenerator[str, None]:
    try:
        if retry_ms is not None:
            yield f"retry: {retry_ms}\n\n"

        while True:
            if await request.is_disconnected():
                logger.info("SSE client disconnected")
                break

            try:
                item = await asyncio.wait_for(writer.queue.get(), timeout=0.25)
            except asyncio.TimeoutError:
                if task.done() and writer.queue.empty():
                    break
                continue

            if item is None:
                break

            yield item

            if task.done() and writer.queue.empty():
                break
    finally:
        await writer.close()
        if not task.done():
            task.cancel()
