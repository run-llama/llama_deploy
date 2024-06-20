import uuid
from enum import Enum
from typing import Any, Dict, List, Optional

from llama_index.core.bridge.pydantic import BaseModel, Field
from llama_index.core.llms import ChatMessage


def generate_id() -> str:
    return str(uuid.uuid4())


CONTROL_PLANE_NAME = "control_plane"


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


class FlowDefinition(BaseModel):
    flow_id: str = Field(default_factory=generate_id)


class ServiceDefinition(BaseModel):
    service_name: str = Field(description="The name of the service.")
    description: str = Field(
        description="A description of the service and it's purpose."
    )
    prompt: List[ChatMessage] = Field(
        default_factory=list, description="Specific instructions for the service."
    )
