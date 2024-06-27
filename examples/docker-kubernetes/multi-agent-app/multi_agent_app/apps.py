from multi_agent_app.core_services.message_queue import app as message_queue
from multi_agent_app.core_services.control_plane import app as control_plane
from multi_agent_app.agent_services.secret_agent import app as secret_agent
from multi_agent_app.agent_services.funny_agent import app as funny_agent
from multi_agent_app.additional_services.human_consumer import app as human_consumer


__all__ = [
    "message_queue",
    "control_plane",
    "secret_agent",
    "funny_agent",
    "human_consumer",
]
