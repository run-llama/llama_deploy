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
    NEW_TASK = "new_task"
    COMPLETED_TASK = "completed_task"
    REQUEST_FOR_HELP = "request_for_help"
    NEW_TOOL_CALL = "new_tool_call"
    COMPLETED_TOOL_CALL = "completed_tool_call"


class TaskDefinition(BaseModel):
    input: str
    task_id: str = Field(default_factory=generate_id)
    state: dict = Field(default_factory=dict)
    agent_id: Optional[str] = None


class TaskResult(BaseModel):
    task_id: str
    history: List[ChatMessage]
    result: str


class ToolCallBundle(BaseModel):
    tool_name: str
    tool_args: List[Any]
    tool_kwargs: Dict[str, Any]


class ToolCall(BaseModel):
    id_: str = Field(default_factory=generate_id)
    tool_call_bundle: ToolCallBundle
    source_id: str


class ToolCallResult(BaseModel):
    id_: str
    tool_message: ChatMessage
    result: str


class ServiceDefinition(BaseModel):
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
    result: str


http_url_adapter = TypeAdapter(HttpUrl)
PydanticValidatedUrl = Annotated[
    str, BeforeValidator(lambda value: str(http_url_adapter.validate_python(value)))
]
