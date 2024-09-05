import uuid
from enum import Enum
from pydantic import BaseModel, Field, BeforeValidator, HttpUrl, TypeAdapter
from pydantic.v1 import BaseModel as V1BaseModel
from typing import Any, Dict, List, Optional, Union
from typing_extensions import Annotated

from llama_index.core.llms import MessageRole


def generate_id() -> str:
    return str(uuid.uuid4())


CONTROL_PLANE_NAME = "control_plane"


class ChatMessage(BaseModel):
    """Chat message.

    TODO: Temp copy of class from llama-index, to avoid pydantic v1/v2 issues.
    """

    role: MessageRole = MessageRole.USER
    content: Optional[Any] = ""
    additional_kwargs: dict = Field(default_factory=dict)

    def __str__(self) -> str:
        return f"{self.role.value}: {self.content}"

    @classmethod
    def from_str(
        cls,
        content: str,
        role: Union[MessageRole, str] = MessageRole.USER,
        **kwargs: Any,
    ) -> "ChatMessage":
        if isinstance(role, str):
            role = MessageRole(role)
        return cls(role=role, content=content, **kwargs)

    def _recursive_serialization(self, value: Any) -> Any:
        if isinstance(value, (V1BaseModel, BaseModel)):
            return value.dict()
        if isinstance(value, dict):
            return {
                key: self._recursive_serialization(value)
                for key, value in value.items()
            }
        if isinstance(value, list):
            return [self._recursive_serialization(item) for item in value]
        return value

    def dict(self, **kwargs: Any) -> dict:
        # ensure all additional_kwargs are serializable
        msg = super().dict(**kwargs)

        for key, value in msg.get("additional_kwargs", {}).items():
            value = self._recursive_serialization(value)
            if not isinstance(value, (str, int, float, bool, dict, list, type(None))):
                raise ValueError(
                    f"Failed to serialize additional_kwargs value: {value}"
                )
            msg["additional_kwargs"][key] = value

        return msg


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
        agent_id (str):
            The agent ID that the task should be sent to.
            If blank, the orchestrator decides.
    """

    input: str
    task_id: str = Field(default_factory=generate_id)
    session_id: Optional[str] = None
    agent_id: Optional[str] = None


class SessionDefinition(BaseModel):
    """
    The definition of a session.

    Attributes:
        session_id (str):
            The session ID. Defaults to a random UUID.
        task_definitions (List[str]):
            The task ids in order, representing the session.
        state (dict):
            The current session state.
    """

    session_id: str = Field(default_factory=generate_id)
    task_ids: List[str] = Field(default_factory=list)
    state: dict = Field(default_factory=dict)

    @property
    def current_task_id(self) -> Optional[str]:
        if len(self.task_ids) == 0:
            return None

        return self.task_ids[-1]


class NewTask(BaseModel):
    """The payload for a new task message."""

    task: TaskDefinition
    state: Dict[str, Any] = Field(default_factory=dict)


class TaskResult(BaseModel):
    """
    The result of a task.

    Attributes:
        task_id (str):
            The task ID.
        history (List[ChatMessage]):
            The task history.
        result (str):
            The task result.
        data (dict):
            Additional data about the task or result.
    """

    task_id: str
    history: List[ChatMessage]
    result: str
    data: dict = Field(default_factory=dict)


class ToolCallBundle(BaseModel):
    """
    A bundle of information for a tool call.

    Attributes:
        tool_name (str):
            The name of the tool.
        tool_args (List[Any]):
            The tool arguments.
        tool_kwargs (Dict[str, Any]):
            The tool keyword arguments
    """

    tool_name: str
    tool_args: List[Any]
    tool_kwargs: Dict[str, Any]


class ToolCall(BaseModel):
    """
    A tool call.

    Attributes:
        id_ (str):
            The tool call ID. Defaults to a random UUID.
        tool_call_bundle (ToolCallBundle):
            The tool call bundle.
        source_id (str):
            The source ID.
    """

    id_: str = Field(default_factory=generate_id)
    tool_call_bundle: ToolCallBundle
    source_id: str


class ToolCallResult(BaseModel):
    """
    A tool call result.

    Attributes:
        id_ (str):
            The tool call ID. Should match the ID of the tool call.
        tool_message (ChatMessage):
            The tool message.
        result (str):
            The tool result.
    """

    id_: str
    tool_message: ChatMessage
    result: str


class ServiceDefinition(BaseModel):
    """
    The definition of a service, bundles useful information describing the service.

    Attributes:
        service_name (str):
            The name of the service.
        description (str):
            A description of the service and it's purpose.
        prompt (List[ChatMessage]):
            Specific instructions for the service.
        host (Optional[str]):
            The host of the service, if its a network service.
        port (Optional[int]):
            The port of the service, if its a network service.
    """

    service_name: str = Field(description="The name of the service.")
    description: str = Field(
        description="A description of the service and it's purpose."
    )
    prompt: List[ChatMessage] = Field(
        default_factory=list, description="Specific instructions for the service."
    )
    host: Optional[str] = None
    port: Optional[int] = None


class HumanResponse(BaseModel):
    """
    A simple human response.

    Attributes:
        response (str):
            The human response.
    """

    result: str


http_url_adapter = TypeAdapter(HttpUrl)
PydanticValidatedUrl = Annotated[
    str, BeforeValidator(lambda value: str(http_url_adapter.validate_python(value)))
]
