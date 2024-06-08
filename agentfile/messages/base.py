"""Base Message."""

import uuid
from typing import Any, Optional
from llama_index.core.bridge.pydantic import BaseModel, Field

from agentfile.types import ActionTypes


class QueueMessage(BaseModel):
    id_: str = Field(default_factory=lambda: str(uuid.uuid4()))
    data: Optional[Any] = Field(default_factory=None)
    action: Optional[ActionTypes] = None
    type: str = Field(
        default="default", description="Type of the message, used for routing."
    )

    class Config:
        arbitrary_types_allowed = True
