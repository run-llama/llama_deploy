import httpx
import reflex as rx
import os
from ..state import State


class SessionState(rx.State):
    # List to store session items
    sessions: list[dict] = []
    # Default text for new items
    default_new_text: str = "New Session"
    # Index of session being edited
    editing_index: int = -1
    # Temporary value for editing
    edit_value: str = ""
    # Currently selected session index
    selected_session_index: int = -1

    async def _create_session(self, name: str):
        client = httpx.AsyncClient()

        deployment_name = os.environ.get("DEPLOYMENT_NAME", "MyDeployment")
        apiserver_url = os.environ.get("APISERVER_URL", "http://localhost:4501")
        response = await client.post(
            f"{apiserver_url}/deployments/{deployment_name}/sessions/create",
            timeout=60,
        )
        data = response.json()
        session_id = data["session_id"]
        return {"id": session_id, "session_name": name}

    async def create_default_session(self):
        if len(self.sessions) == 0:
            session = await self._create_session("Default")
            self.sessions.append(session)
            await self.select_session(0)

    async def select_session(self, index: int):
        self.selected_session_index = index
        return State.update_chat_history(self.selected_session_id)

    @rx.var
    def selected_session_id(self) -> str | None:
        if self.selected_session_index == -1:
            return None
        return self.sessions[self.selected_session_index]["id"]

    def add_session(self):
        self.sessions.append(self.default_new_text)
        # Automatically start editing the new item
        self.start_edit(len(self.sessions) - 1)

    def start_edit(self, index: int):
        self.editing_index = index
        self.edit_value = self.sessions[index]

    async def save_edit(self):
        if self.edit_value.strip():
            session = await self._create_session(self.edit_value)
            self.sessions[self.editing_index] = session
        self.editing_index = -1
        self.edit_value = ""

    def handle_key_press(self, key: str):
        if key == "Enter":
            self.save_edit()
        elif key == "Escape":
            self.save_edit()
