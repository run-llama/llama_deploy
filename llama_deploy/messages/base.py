"""Base Message."""

import uuid
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from typing import Any, Dict, Optional

from llama_deploy.types import ActionTypes


class QueueMessageStats(BaseModel):
    """Stats for a queue message.

    Attributes:
        publish_time (Optional[str]):
            The time the message was published.
        process_start_time (Optional[str]):
            The time the message processing started.
        process_end_time (Optional[str]):
            The time the message processing ended.
    """

    publish_time: Optional[str] = Field(default=None)
    process_start_time: Optional[str] = Field(default=None)
    process_end_time: Optional[str] = Field(default=None)

    @staticmethod
    def timestamp_str(format: str = "%Y-%m-%d %H:%M:%S") -> str:
        return datetime.now().strftime(format)


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
    action: Optional[ActionTypes] = None
    stats: QueueMessageStats = Field(default_factory=QueueMessageStats)
    type: str = Field(
        default="default", description="Type of the message, used for routing."
    )
