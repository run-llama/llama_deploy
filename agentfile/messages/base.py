"""Base Message."""

import uuid
from typing import Any, Optional
from llama_index.core.bridge.pydantic import BaseModel, Field


class QueueMessage(BaseModel):
    id_: str = Field(default_factory=lambda: str(uuid.uuid4))
    data: Optional[Any] = Field(default_factory=None)
    type: str = Field(
        default="default", description="Type of the message, used for routing."
    )
    action: str = Field(
        default_factory=str, description="Action of message, used for processing."
    )

    class Config:
        arbitrary_types_allowed = True
