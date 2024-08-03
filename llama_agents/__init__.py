from llama_agents.client import AsyncLlamaAgentsClient, LlamaAgentsClient
from llama_agents.control_plane import ControlPlaneServer
from llama_agents.launchers import LocalLauncher, ServerLauncher
from llama_agents.message_consumers import CallableMessageConsumer
from llama_agents.message_queues import SimpleMessageQueue
from llama_agents.messages import QueueMessage
from llama_agents.orchestrators import (
    AgentOrchestrator,
    PipelineOrchestrator,
    OrchestratorRouter,
)
from llama_agents.tools import (
    AgentServiceTool,
    MetaServiceTool,
    ServiceAsTool,
    ServiceComponent,
    ServiceTool,
)
from llama_agents.services import (
    AgentService,
    ToolService,
    HumanService,
    ComponentService,
)

# configure logger
import logging

root_logger = logging.getLogger("llama_agents")

formatter = logging.Formatter("%(levelname)s:%(name)s - %(message)s")
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
root_logger.addHandler(console_handler)

root_logger.setLevel(logging.INFO)
root_logger.propagate = False


__all__ = [
    # clients
    "LlamaAgentsClient",
    "AsyncLlamaAgentsClient",
    # services
    "AgentService",
    "HumanService",
    "ToolService",
    "ComponentService",
    # messages
    "QueueMessage",
    # message consumers
    "CallableMessageConsumer",
    # message queues
    "SimpleMessageQueue",
    # launchers
    "LocalLauncher",
    "ServerLauncher",
    # control planes
    "ControlPlaneServer",
    # orchestrators
    "AgentOrchestrator",
    "PipelineOrchestrator",
    "OrchestratorRouter",
    # various utils
    "AgentServiceTool",
    "ServiceAsTool",
    "ServiceComponent",
    "ServiceTool",
    "MetaServiceTool",
]
