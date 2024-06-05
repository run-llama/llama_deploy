"""Base Message."""

import uuid
from typing import Any, Optional
from llama_index.core.bridge.pydantic import BaseModel, Field


class BaseMessage(BaseModel):
    id_: str = Field(default_factory=uuid.uuid4)
    data: Optional[Any] = Field(default_factory=None)

    @classmethod
    def class_name(cls) -> str:
        """Class name."""
        return "BaseMessage"

    class Config:
        arbitrary_types_allowed = True
