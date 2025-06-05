import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict

from llama_index.core.llms import ChatMessage
from pydantic import BaseModel, ConfigDict, Field


def generate_id() -> str:
    return str(uuid.uuid4())


CONTROL_PLANE_NAME = "control_plane"


class ActionTypes(str, Enum):
    """
    Action types for messages.
    Different consumers will handle (or ignore) different action types.
    """

    NEW_TASK = "new_task"
    COMPLETED_TASK = "completed_task"
    REQUEST_FOR_HELP = "request_for_help"
    NEW_TOOL_CALL = "new_tool_call"
    COMPLETED_TOOL_CALL = "completed_tool_call"
    TASK_STREAM = "task_stream"
    SEND_EVENT = "send_event"


class QueueMessageStats(BaseModel):
    """Stats for a queue message.

    Attributes:
        publish_time (Optional[str]):
            The time the message was published.
        process_start_time (Optional[str]):
            The time the message processing started.
        process_end_time (Optional[str]):
            The time the message processing ended.
        trace_id (Optional[str]):
            The trace ID for distributed tracing.
        span_id (Optional[str]):
            The span ID for distributed tracing.
    """

    publish_time: str | None = Field(default=None)
    process_start_time: str | None = Field(default=None)
    process_end_time: str | None = Field(default=None)
    trace_id: str | None = Field(default=None)
    span_id: str | None = Field(default=None)

    @staticmethod
    def timestamp_str(format: str = "%Y-%m-%d %H:%M:%S") -> str:
        return datetime.now().strftime(format)

    def set_trace_context(self) -> None:
        """Set trace context from current span if tracing is enabled."""
        try:
            from opentelemetry import trace

            current_span = trace.get_current_span()
            if current_span and current_span.is_recording():
                ctx = current_span.get_span_context()
                self.trace_id = format(ctx.trace_id, "032x")
                self.span_id = format(ctx.span_id, "016x")
        except ImportError:
            # OpenTelemetry not available
            pass
        except Exception:
            # Silently ignore tracing errors
            pass


class QueueMessage(BaseModel):
    """A message for the message queue.

    Attributes:
        id_ (str):
            The id of the message.
        publisher_id (str):
            The id of the publisher.
        data (Dict[str, Any]):
            The data of the message.
        action (Optional[ActionTypes]):
            The action of the message, used for deciding how to process the message.
        stats (QueueMessageStats):
            The stats of the message.
        type (str):
            The type of the message. Typically this is a service name.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id_: str = Field(default_factory=lambda: str(uuid.uuid4()))
    publisher_id: str = Field(default="default", description="Id of publisher.")
    data: Dict[str, Any] = Field(default_factory=dict)
    action: ActionTypes | None = None
    stats: QueueMessageStats = Field(default_factory=QueueMessageStats)
    type: str = Field(
        default="default", description="Type of the message, used for routing."
    )


class TaskDefinition(BaseModel):
    """
    The definition and state of a task.

    Attributes:
        input (str):
            The task input.
        session_id (str):
            The session ID that the task belongs to.
        task_id (str):
            The task ID. Defaults to a random UUID.
        service_id (str):
            The service ID that the task should be sent to.
            If blank, the orchestrator decides.
    """

    input: str
    task_id: str = Field(default_factory=generate_id)
    session_id: str | None = None
    service_id: str | None = None


class SessionDefinition(BaseModel):
    """
    The definition of a session.

    Attributes:
        session_id (str):
            The session ID. Defaults to a random UUID.
        task_definitions (list[str]):
            The task ids in order, representing the session.
        state (dict):
            The current session state.
    """

    session_id: str = Field(default_factory=generate_id)
    task_ids: list[str] = Field(default_factory=list)
    state: dict = Field(default_factory=dict)


class EventDefinition(BaseModel):
    """The definition of event.

    To be used as payloads for service endpoints when wanting to send serialized
    Events.

    Attributes:
        event_object_str (str): serialized string of event.
    """

    service_id: str
    event_obj_str: str


class TaskResult(BaseModel):
    """
    The result of a task.

    Attributes:
        task_id (str):
            The task ID.
        history (list[ChatMessage]):
            The task history.
        result (str):
            The task result.
        data (dict):
            Additional data about the task or result.
    """

    task_id: str
    history: list[ChatMessage]
    result: str
    data: dict = Field(default_factory=dict)


class TaskStream(BaseModel):
    """
    A stream of data generated by a task.

    Attributes:
        task_id (str):
            The associated task ID.
        data (list[dict]):
            The stream data.
        index (int):
            The index of the stream data.
    """

    task_id: str
    session_id: str | None
    data: dict
    index: int


class ServiceDefinition(BaseModel):
    """
    The definition of a service, bundles useful information describing the service.

    Attributes:
        service_name (str):
            The name of the service.
        description (str):
            A description of the service and it's purpose.
        prompt (list[ChatMessage]):
            Specific instructions for the service.
        host (str | None):
            The host of the service, if its a network service.
        port (int | None):
            The port of the service, if its a network service.
    """

    service_name: str = Field(description="The name of the service.")
    description: str = Field(
        description="A description of the service and it's purpose."
    )
    prompt: list[ChatMessage] = Field(
        default_factory=list, description="Specific instructions for the service."
    )
    host: str | None = None
    port: int | None = None


class HumanResponse(BaseModel):
    """
    A simple human response.

    Attributes:
        response (str):
            The human response.
    """

    result: str
