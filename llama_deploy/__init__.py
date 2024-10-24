# configure logger
import logging

from llama_deploy.client import AsyncLlamaDeployClient, Client, LlamaDeployClient
from llama_deploy.control_plane import ControlPlaneConfig, ControlPlaneServer
from llama_deploy.deploy import deploy_core, deploy_workflow
from llama_deploy.message_consumers import CallableMessageConsumer
from llama_deploy.message_queues import SimpleMessageQueue, SimpleMessageQueueConfig
from llama_deploy.messages import QueueMessage
from llama_deploy.orchestrators import SimpleOrchestrator, SimpleOrchestratorConfig
from llama_deploy.services import (
    AgentService,
    ComponentService,
    HumanService,
    ToolService,
    WorkflowService,
    WorkflowServiceConfig,
)
from llama_deploy.tools import (
    AgentServiceTool,
    MetaServiceTool,
    ServiceAsTool,
    ServiceComponent,
    ServiceTool,
)

root_logger = logging.getLogger("llama_deploy")

formatter = logging.Formatter("%(levelname)s:%(name)s - %(message)s")
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
root_logger.addHandler(console_handler)

root_logger.setLevel(logging.INFO)
root_logger.propagate = False


__all__ = [
    # clients
    "LlamaDeployClient",
    "AsyncLlamaDeployClient",
    "Client",
    # services
    "AgentService",
    "HumanService",
    "ToolService",
    "ComponentService",
    "WorkflowService",
    "WorkflowServiceConfig",
    # messages
    "QueueMessage",
    # message consumers
    "CallableMessageConsumer",
    # message queues
    "SimpleMessageQueue",
    "SimpleMessageQueueConfig",
    # deployment
    "deploy_core",
    "deploy_workflow",
    # control planes
    "ControlPlaneServer",
    "ControlPlaneConfig",
    # orchestrators
    "SimpleOrchestrator",
    "SimpleOrchestratorConfig",
    # various utils
    "AgentServiceTool",
    "ServiceAsTool",
    "ServiceComponent",
    "ServiceTool",
    "MetaServiceTool",
]
