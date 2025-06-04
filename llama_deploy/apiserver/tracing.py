"""Tracing utilities for llama_deploy."""

import logging
from contextlib import contextmanager, nullcontext
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, Generator, TypeVar

if TYPE_CHECKING:
    from llama_deploy.apiserver.settings import ApiserverSettings


logger = logging.getLogger(__name__)

# Since opentelemetry is optional, we have to use Any to type the tracer
_tracer: Any | None = None
_tracing_enabled = False
_null_context = nullcontext()

F = TypeVar("F", bound=Callable[..., Any])


def configure_tracing(settings: "ApiserverSettings") -> None:
    """Configure OpenTelemetry tracing based on the provided configuration."""
    global _tracer, _tracing_enabled

    if not settings.tracing_enabled:
        logger.debug("Tracing is disabled")
        _tracing_enabled = False
        return

    try:
        from opentelemetry import trace
        from opentelemetry.instrumentation.asyncio import AsyncioInstrumentor
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

        # Create resource with service name
        resource = Resource.create({SERVICE_NAME: settings.tracing_service_name})

        # Create tracer provider with sampling
        tracer_provider = TracerProvider(
            resource=resource, sampler=TraceIdRatioBased(settings.tracing_sample_rate)
        )

        # Configure exporter based on config
        if settings.tracing_exporter == "console":
            from opentelemetry.sdk.trace.export import ConsoleSpanExporter

            exporter = ConsoleSpanExporter()

        elif settings.tracing_exporter == "otlp":
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )

            if not settings.tracing_endpoint:
                raise ValueError("OTLP exporter requires an endpoint")
            exporter = OTLPSpanExporter(
                endpoint=f"{settings.tracing_endpoint}/v1/traces",
                insecure=settings.tracing_insecure,
                timeout=settings.tracing_timeout,
            )
        else:
            raise ValueError(f"Unsupported exporter: {settings.tracing_exporter}")

        # Add span processor
        span_processor = BatchSpanProcessor(exporter)
        tracer_provider.add_span_processor(span_processor)

        # Set the global tracer provider
        trace.set_tracer_provider(tracer_provider)

        # Initialize global tracer
        _tracer = trace.get_tracer(__name__)
        _tracing_enabled = True

        # Setup auto-instrumentation
        AsyncioInstrumentor().instrument()

        logger.info(
            f"Tracing configured with {settings.tracing_exporter} exporter, service: {settings.tracing_service_name}"
        )

    except ImportError as e:
        msg = (
            f"Tracing is enabled but OpenTelemetry instrumentation packages are missing: {e}. "
            "Run `pip install llama_deploy[observability]`"
        )
        logger.warning(msg)
        _tracing_enabled = False
    except Exception as e:
        logger.error(f"Failed to configure tracing: {e}")
        _tracing_enabled = False


def get_tracer() -> Any | None:
    """Get the configured tracer instance."""
    return _tracer if _tracing_enabled else None


def is_tracing_enabled() -> bool:
    """Check if tracing is enabled."""
    return _tracing_enabled


def trace_method(
    span_name: str | None = None, attributes: dict | None = None
) -> Callable[[F], F]:
    """Decorator to add tracing to synchronous methods."""

    def decorator(func: F) -> F:
        if not _tracing_enabled:
            return func

        @wraps(func)
        def wrapper(*args, **kwargs):  # type: ignore
            tracer = get_tracer()
            if not tracer:
                return func(*args, **kwargs)

            name = span_name or f"{func.__module__}.{func.__qualname__}"
            with tracer.start_as_current_span(name) as span:
                if attributes:
                    span.set_attributes(attributes)

                if hasattr(func, "__annotations__"):
                    for i, (param_name, _) in enumerate(func.__annotations__.items()):
                        if i < len(args) and param_name not in {"self", "cls"}:
                            span.set_attribute(
                                f"arg.{param_name}", str(args[i])[:100]
                            )  # Truncate long values

                try:
                    result = func(*args, **kwargs)
                    span.set_attribute("success", True)
                    return result
                except Exception as e:
                    span.set_attribute("success", False)
                    span.set_attribute("error.type", type(e).__name__)
                    span.set_attribute("error.message", str(e))
                    raise

        return wrapper  # type: ignore

    return decorator


def trace_async_method(
    span_name: str | None = None, attributes: dict | None = None
) -> Callable[[F], F]:
    """Decorator to add tracing to asynchronous methods."""

    def decorator(func: F) -> F:
        if not _tracing_enabled:
            return func

        @wraps(func)
        async def wrapper(*args, **kwargs):  # type: ignore
            tracer = get_tracer()
            if not tracer:
                return await func(*args, **kwargs)

            name = span_name or f"{func.__module__}.{func.__qualname__}"
            with tracer.start_as_current_span(name) as span:
                if attributes:
                    span.set_attributes(attributes)

                if hasattr(func, "__annotations__"):
                    for i, (param_name, _) in enumerate(func.__annotations__.items()):
                        if i < len(args) and param_name not in {"self", "cls"}:
                            span.set_attribute(
                                f"arg.{param_name}", str(args[i])[:100]
                            )  # Truncate long values

                try:
                    result = await func(*args, **kwargs)
                    span.set_attribute("success", True)
                    return result
                except Exception as e:
                    span.set_attribute("success", False)
                    span.set_attribute("error.type", type(e).__name__)
                    span.set_attribute("error.message", str(e))
                    raise

        return wrapper  # type: ignore

    return decorator


@contextmanager
def create_span(
    name: str, attributes: dict | None = None
) -> Generator[Any, None, None]:
    tracer = get_tracer()
    if tracer is None:
        yield
        return

    with tracer.start_as_current_span(name) as span:
        if attributes:
            for k, v in attributes.items():
                span.set_attribute(k, v)
        yield span


def add_span_attribute(key: str, value: Any) -> None:
    """Add an attribute to the current span if tracing is enabled."""
    if not _tracing_enabled:
        return

    try:
        from opentelemetry import trace

        current_span = trace.get_current_span()
        if current_span:
            current_span.set_attribute(key, str(value))
    except Exception:
        # Silently ignore tracing errors
        pass


def add_span_event(name: str, attributes: dict | None = None) -> None:
    """Add an event to the current span if tracing is enabled."""
    if not _tracing_enabled:
        return

    try:
        from opentelemetry import trace

        current_span = trace.get_current_span()
        if current_span:
            current_span.add_event(name, attributes or {})
    except Exception:
        # Silently ignore tracing errors
        pass
