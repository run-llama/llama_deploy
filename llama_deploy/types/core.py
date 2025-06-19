import uuid

from llama_index.core.llms import ChatMessage
from pydantic import BaseModel, Field


def generate_id() -> str:
    return str(uuid.uuid4())


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
