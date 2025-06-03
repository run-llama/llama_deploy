"""Tracing module for llama_deploy API server."""

from .middleware import setup_tracing
from .utils import (
    add_span_attribute,
    add_span_event,
    configure_tracing,
    get_tracer,
    trace_async_method,
    trace_method,
)

__all__ = [
    "configure_tracing",
    "get_tracer",
    "trace_method",
    "trace_async_method",
    "setup_tracing",
    "add_span_attribute",
    "add_span_event",
]
