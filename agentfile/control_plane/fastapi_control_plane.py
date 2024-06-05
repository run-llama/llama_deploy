from typing import Any, Dict

from agentfile.control_plane.base import BaseControlPlane


class FastAPIControlPlane(BaseControlPlane):
    def __init__(self) -> None:
        self.agents: Dict[str, Any] = {}
        self.flows: Dict[str, Any] = {}
        self.tasks: Dict[str, Any] = {}

    def register_agent(self, agent_id: str, agent_role: str) -> None:
        self.agents[agent_id] = agent_role

    def deregister_agent(self, agent_id: str) -> None:
        del self.agents[agent_id]

    def register_flow(self, flow_id: str, flow_definition: dict) -> None:
        self.flows[flow_id] = flow_definition

    def deregister_flow(self, flow_id: str) -> None:
        del self.flows[flow_id]

    def handle_new_task(self, task_id: str, task_definition: dict) -> None:
        self.tasks[task_id] = task_definition

    def send_task_to_agent(self, task_id: str, agent_id: str) -> None:
        pass

    def handle_agent_completion(
        self, task_id: str, agent_id: str, result: dict
    ) -> None:
        pass

    def get_next_agent(self, task_id: str) -> str:
        return ""

    def get_task_state(self, task_id: str) -> dict:
        return self.tasks.get(task_id, None)

    def request_user_input(self, task_id: str, message: str) -> None:
        pass

    def handle_user_input(self, task_id: str, user_input: str) -> None:
        pass
