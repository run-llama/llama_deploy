"""Base Message."""

import uuid
from datetime import datetime
from typing import Any, Optional
from llama_index.core.bridge.pydantic import BaseModel, Field

from agentfile.types import ActionTypes


class QueueMessageStats(BaseModel):
    publish_time: Optional[str] = Field(default=None)
    process_start_time: Optional[str] = Field(default=None)
    process_end_time: Optional[str] = Field(default=None)

    @staticmethod
    def timestamp_str(format: str = "%Y-%m-%d %H:%M:%S") -> str:
        return datetime.now().strftime(format)


class QueueMessage(BaseModel):
    id_: str = Field(default_factory=lambda: str(uuid.uuid4()))
    publisher_id: str = Field(default="default", description="Id of publisher.")
    data: Optional[Any] = Field(default_factory=None)
    action: Optional[ActionTypes] = None
    stats: QueueMessageStats = Field(default_factory=QueueMessageStats)
    type: str = Field(
        default="default", description="Type of the message, used for routing."
    )

    class Config:
        arbitrary_types_allowed = True
