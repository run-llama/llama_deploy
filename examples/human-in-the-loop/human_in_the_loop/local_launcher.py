from llama_agents import ServerLauncher

from human_in_the_loop.core_services.message_queue import message_queue
from human_in_the_loop.core_services.control_plane import control_plane
from human_in_the_loop.agent_services.funny_agent import agent_server
from human_in_the_loop.additional_services.human_in_the_loop import human_service


# launch it
launcher = ServerLauncher(
    [agent_server, human_service],
    control_plane,
    message_queue,
)


if __name__ == "__main__":
    launcher.launch_servers()
