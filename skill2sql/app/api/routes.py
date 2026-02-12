"""HTTP 路由定义。"""

import asyncio
from typing import Any
from uuid import uuid4

from pydantic import ValidationError
from sse_starlette.sse import EventSourceResponse
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from ..common.datasource_util import DatasourceError, parse_datasource
from ..core.auth import require_api_key
from ..core.config import settings
from ..core.sse import SSEWriter, format_sse_message, sse_event_stream
from ..deepagent.deep_research_agent import DeepAgent
from ..schemas.requests import ReportRunRequest, ReportStopRequest
from ..schemas.responses import DataTypeEnum

_agent = DeepAgent()


async def health(_request: Request):
    return JSONResponse({"status": "ok"})


async def report_run(request: Request):
    auth_error = require_api_key(request)
    if auth_error:
        return auth_error

    try:
        payload: Any = await request.json()
    except Exception:
        return JSONResponse({"detail": "Invalid JSON"}, status_code=400)

    try:
        req = ReportRunRequest.model_validate(payload)
    except ValidationError as exc:
        return JSONResponse({"detail": exc.errors()}, status_code=422)

    try:
        datasource = parse_datasource(req.datasource.model_dump())
    except DatasourceError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=400)

    llm_config = req.llm.model_dump()
    options = req.options.model_dump(exclude_none=True) if req.options else None

    task_id = req.uuid or req.chat_id or f"task-{uuid4().hex}"
    session_id = req.chat_id or task_id

    writer = SSEWriter()

    async def _run_agent():
        await _agent.run_agent(
            query=req.query,
            response=writer,
            session_id=session_id,
            task_id=task_id,
            datasource=datasource,
            llm_config=llm_config,
            skills=req.skills,
            options=options,
        )

    agent_task = asyncio.create_task(_run_agent())

    async def _event_stream():
        yield format_sse_message(
            task_id,
            message_type="info",
            data_type=DataTypeEnum.TASK_ID.value[0],
        )
        async for chunk in sse_event_stream(
            request, writer, agent_task, retry_ms=settings.sse_retry_ms
        ):
            yield chunk

    return EventSourceResponse(_event_stream())


async def report_stop(request: Request):
    auth_error = require_api_key(request)
    if auth_error:
        return auth_error

    try:
        payload: Any = await request.json()
    except Exception:
        return JSONResponse({"detail": "Invalid JSON"}, status_code=400)

    try:
        req = ReportStopRequest.model_validate(payload)
    except ValidationError as exc:
        return JSONResponse({"detail": exc.errors()}, status_code=422)

    cancelled = await _agent.cancel_task(req.task_id)
    return JSONResponse({"task_id": req.task_id, "cancelled": cancelled})


routes = [
    Route("/health", health, methods=["GET"]),
    Route("/report/run", report_run, methods=["POST"]),
    Route("/report/stop", report_stop, methods=["POST"]),
]
