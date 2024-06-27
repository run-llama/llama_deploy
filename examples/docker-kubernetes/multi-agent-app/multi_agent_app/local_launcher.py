from llama_agents import ServerLauncher

from multi_agent_app.core_services.message_queue import message_queue
from multi_agent_app.core_services.control_plane import control_plane
from multi_agent_app.agent_services.secret_agent import (
    agent_server as secret_agent_server,
)
from multi_agent_app.agent_services.funny_agent import (
    agent_server as funny_agent_server,
)
from multi_agent_app.additional_services.human_consumer import human_consumer_server


# launch it
launcher = ServerLauncher(
    [secret_agent_server, funny_agent_server],
    control_plane,
    message_queue,
    additional_consumers=[human_consumer_server.as_consumer()],
)

launcher.launch_servers()
