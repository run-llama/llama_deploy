import asyncio
import json
from typing import Any, AsyncGenerator, TextIO

import httpx

from llama_deploy.types.apiserver import Status, StatusEnum
from llama_deploy.types.core import TaskDefinition, TaskResult

from .model import Collection, Model

DEFAULT_POLL_INTERVAL = 0.5


class Session(Model):
    pass


class SessionCollection(Collection):
    deployment_id: str

    async def delete(self, session_id: str) -> None:
        settings = self.client.settings
        delete_url = f"{settings.api_server_url}/deployments/{self.deployment_id}/sessions/delete"

        await self.client.request(
            "POST",
            delete_url,
            params={"session_id": session_id},
            verify=not settings.disable_ssl,
            timeout=settings.timeout,
        )


class Task(Model):
    deployment_id: str

    async def results(self, session_id: str) -> TaskResult:
        settings = self.client.settings
        results_url = f"{settings.api_server_url}/deployments/{self.deployment_id}/tasks/{self.id}/results"

        r = await self.client.request(
            "GET",
            results_url,
            verify=not settings.disable_ssl,
            params={"session_id": session_id},
            timeout=settings.timeout,
        )
        return TaskResult.model_validate_json(r.json())

    async def events(self, session_id: str) -> AsyncGenerator[dict[str, Any], None]:
        settings = self.client.settings
        events_url = f"{settings.api_server_url}/deployments/{self.deployment_id}/tasks/{self.id}/events"

        while True:
            try:
                async with httpx.AsyncClient(verify=not settings.disable_ssl) as client:
                    async with client.stream(
                        "GET", events_url, params={"session_id": session_id}
                    ) as response:
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            json_line = json.loads(line)
                            yield json_line
                        break  # Exit the function if successful
            except httpx.HTTPStatusError as e:
                if e.response.status_code != 404:
                    raise  # Re-raise if it's not a 404 error
                await asyncio.sleep(DEFAULT_POLL_INTERVAL)


class TaskCollection(Collection):
    deployment_id: str

    async def run(self, task: TaskDefinition) -> Any:
        settings = self.client.settings
        run_url = (
            f"{settings.api_server_url}/deployments/{self.deployment_id}/tasks/run"
        )

        r = await self.client.request(
            "POST",
            run_url,
            verify=not settings.disable_ssl,
            json=task.model_dump_json(),
            timeout=settings.timeout,
        )

        return r.json()

    async def create(self, task: TaskDefinition) -> Session:
        settings = self.client.settings
        create_url = (
            f"{settings.api_server_url}/deployments/{self.deployment_id}/tasks/create"
        )

        r = await self.client.request(
            "POST",
            create_url,
            verify=not settings.disable_ssl,
            json=task.model_dump_json(),
            timeout=settings.timeout,
        )

        return Session.model_validate(r.json())


class Deployment(Model):
    async def tasks(self) -> TaskCollection:
        settings = self.client.settings
        tasks_url = f"{settings.api_server_url}/deployments/{self.id}/tasks"
        raise NotImplementedError(f"FIXME: Method missing from apiserver: {tasks_url}")

    async def sessions(self) -> SessionCollection:
        settings = self.client.settings
        sessions_url = f"{settings.api_server_url}/deployments/{self.id}/sessions"
        r = await self.client.request(
            "GET",
            sessions_url,
            verify=not settings.disable_ssl,
            timeout=settings.timeout,
        )
        items = {"id": Session(client=self.client, id=name) for name in r.json()}
        return SessionCollection(client=self.client, deployment_id=self.id, items=items)


class DeploymentCollection(Collection):
    async def create(self, config: TextIO) -> None:
        """Creates a deployment"""
        settings = self.client.settings
        create_url = f"{settings.api_server_url}/deployments/create"

        files = {"config": config.read()}
        await self.client.request(
            "POST",
            create_url,
            files=files,
            verify=not settings.disable_ssl,
            timeout=settings.timeout,
        )

    async def get(self, deployment_id: str) -> Deployment:
        """Get a deployment by id"""
        settings = self.client.settings
        get_url = f"{settings.api_server_url}/deployments/{deployment_id}"
        r = await self.client.request(
            "GET", get_url, verify=not settings.disable_ssl, timeout=settings.timeout
        )
        return Deployment.model_validate(r.json())


class ApiServer(Model):
    async def status(self) -> Status:
        """Returns the status of the API Server."""
        settings = self.client.settings
        status_url = f"{settings.api_server_url}/status/"

        r = await self.client.request(
            "GET", status_url, verify=not settings.disable_ssl, timeout=settings.timeout
        )

        if r is None:
            return Status(
                status=StatusEnum.DOWN,
                status_message="API Server is down",
            )

        if r.status_code >= 400:
            body = r.json()
            return Status(status=StatusEnum.UNHEALTHY, status_message=r.text)

        description = "Llama Deploy is up and running."
        body = r.json()
        if deployments := body.get("deployments"):
            description += "\nActive deployments:"
            for d in deployments:
                description += f"- {d}"
        else:
            description += "\nCurrently there are no active deployments"

        return Status(status=StatusEnum.HEALTHY, status_message=description)

    async def deployments(self) -> DeploymentCollection:
        settings = self.client.settings
        status_url = f"{settings.api_server_url}/deployments"

        r = await self.client.request(
            "GET", status_url, verify=not settings.disable_ssl, timeout=settings.timeout
        )
        deployments = {
            "id": Deployment(client=self.client, id=name) for name in r.json()
        }
        return DeploymentCollection(client=self.client, items=deployments)
