"""Skill2SQL app entrypoint."""

from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware

from .api.routes import routes
from .core.config import settings

app = Starlette(debug=False, routes=routes)

if settings.cors_allow_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
        allow_credentials=True,
    )
