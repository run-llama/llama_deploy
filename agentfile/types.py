import uuid
from enum import Enum
from typing import List, Optional

from llama_index.core.bridge.pydantic import BaseModel, Field
from llama_index.core.llms import ChatMessage


def generate_id() -> str:
    return str(uuid.uuid4())


class ActionTypes(str, Enum):
    NEW_TASK = "new_task"
    COMPLETED_TASK = "completed_task"
    REQUEST_FOR_HELP = "request_for_help"


class TaskDefinition(BaseModel):
    input: str
    task_id: str = Field(default_factory=generate_id)
    agent_id: Optional[str] = None


class TaskResult(BaseModel):
    task_id: str
    history: List[ChatMessage]
    result: str


class FlowDefinition(BaseModel):
    flow_id: str = Field(default_factory=generate_id)


class AgentDefinition(BaseModel):
    agent_id: str = Field(description="The name of the agent.")
    description: str = Field(description="A description of the agent and it's purpose.")
    prompt: List[ChatMessage] = Field(
        default_factory=list, description="Specific instructions for the agent."
    )
