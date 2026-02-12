"""简单 API Key 校验。"""

from typing import Optional

from starlette.requests import Request
from starlette.responses import JSONResponse

from .config import settings


def _extract_token(request: Request) -> Optional[str]:
    auth = request.headers.get("authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()

    api_key = request.headers.get("x-api-key")
    if api_key:
        return api_key.strip()

    return None


def require_api_key(request: Request):
    if not settings.api_key:
        return None

    token = _extract_token(request)
    if token and token == settings.api_key:
        return None

    return JSONResponse({"detail": "Unauthorized"}, status_code=401)
