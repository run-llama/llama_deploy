"""Tracing middleware for API server."""

from typing import TYPE_CHECKING

from fastapi import FastAPI

if TYPE_CHECKING:
    from llama_deploy.apiserver.settings import ApiserverSettings

from .utils import configure_tracing


def setup_tracing(app: FastAPI, config: "ApiserverSettings") -> None:
    """Setup OpenTelemetry tracing for FastAPI application."""
    if not config.tracing_enabled:
        return

    # Configure tracing
    configure_tracing(config)

    try:
        # Auto-instrument FastAPI
        from opentelemetry.instrumentation.fastapi import (  # type: ignore
            FastAPIInstrumentor,
        )

        FastAPIInstrumentor.instrument_app(app)

        # Auto-instrument HTTP clients
        from opentelemetry.instrumentation.httpx import (  # type: ignore
            HTTPXClientInstrumentor,
        )

        HTTPXClientInstrumentor().instrument()

        # Auto-instrument asyncio
        from opentelemetry.instrumentation.asyncio import (  # type: ignore
            AsyncioInstrumentor,
        )

        AsyncioInstrumentor().instrument()

    except ImportError:
        # OpenTelemetry instrumentation packages not available
        pass
