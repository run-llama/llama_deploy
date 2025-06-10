"""
Vanilla pydantic serialization isn't sufficient for deep understanding of
event structures in consumers. There's a fair amount of type level information
lost that is helpful to be able to access programmatically in e.g. JavaScript UIs
"""

import logging
from typing import Any, Literal, Optional

from llama_index.core.workflow import (
    Event,
    InputRequiredEvent,
    StartEvent,
    StopEvent,
)

logger = logging.getLogger(__name__)


def serialize_event(event: Event) -> dict[str, Any]:
    """Serialize an event to a dictionary with additional metadata."""
    trait: Optional[Literal["start", "stop", "wait"]] = None
    if isinstance(event, StartEvent):
        trait = "start"
    elif isinstance(event, StopEvent):
        trait = "stop"
    elif isinstance(event, InputRequiredEvent):
        trait = "wait"
    metadata = {
        "type": event.__class__.__name__,
        "trait": trait,
    }
    dumped = event.model_dump()
    if "event_model" in dumped:
        logger.warning(
            "Event already has event_model metadata, this will be overridden"
        )
    return {**dumped, "event_model": metadata}
