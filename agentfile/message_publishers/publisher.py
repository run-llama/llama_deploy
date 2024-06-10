import uuid
from abc import ABC
from typing import Any


class MessageQueuePublisherMixin(ABC):
    """PublisherMixing."""

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        if not hasattr(self, "id_"):
            self.id_ = f"{self.__class__.__qualname__}-{uuid.uuid4()}"
