"""Client functionalities to operate on the Control Plane.

This module allows the client to use all the functionalities
from the Control Plane. For this to work, the Control Plane
must be up and its URL (by default `http://localhost:8000`)
reachable by the host executing the client code.
"""

import asyncio
import json
import time
from typing import Any, AsyncGenerator

import httpx
from llama_index.core.workflow import Event
from llama_index.core.workflow.context_serializers import JsonSerializer

from llama_deploy.types.core import (
    EventDefinition,
    ServiceDefinition,
    TaskDefinition,
    TaskResult,
)

from .model import Collection, Model


class Session(Model):
    """A model representing a Session."""

    async def run(self, service_name: str, **run_kwargs: Any) -> str:
        """Implements the workflow-based run API for a session."""
        task_input = json.dumps(run_kwargs)
        task_def = TaskDefinition(input=task_input, service_id=service_name)
        task_id = await self._do_create_task(task_def)

        # wait for task to complete, up to timeout seconds
        async def _get_result() -> str:
            while True:
                task_result = await self._do_get_task_result(task_id)

                if isinstance(task_result, TaskResult):
                    return task_result.result or ""
                await asyncio.sleep(self.client.poll_interval)

        return await asyncio.wait_for(_get_result(), timeout=self.client.timeout)

    async def run_nowait(self, service_name: str, **run_kwargs: Any) -> str:
        """Implements the workflow-based run API for a session, but does not wait for the task to complete."""

        task_input = json.dumps(run_kwargs)
        task_def = TaskDefinition(input=task_input, service_id=service_name)
        task_id = await self._do_create_task(task_def)

        return task_id

    async def create_task(self, task_def: TaskDefinition) -> str:
        """Create a new task in this session.

        Args:
            task_def (TaskDefinition): The task definition.

        Returns:
            str: The ID of the created task.
        """
        return await self._do_create_task(task_def)

    async def _do_create_task(self, task_def: TaskDefinition) -> str:
        """Async-only version of create_task, to be used internally from other methods."""
        task_def.session_id = self.id
        url = f"{self.client.control_plane_url}/sessions/{self.id}/tasks"
        response = await self.client.request("POST", url, json=task_def.model_dump())
        return response.json()

    async def get_task_result(self, task_id: str) -> TaskResult | None:
        """Get the result of a task in this session if it has one.

        Args:
            task_id (str): The ID of the task to get the result for.

        Returns:
            Optional[TaskResult]: The result of the task if it has one, otherwise None.
        """
        return await self._do_get_task_result(task_id)

    async def _do_get_task_result(self, task_id: str) -> TaskResult | None:
        """Async-only version of get_task_result, to be used internally from other methods."""
        url = (
            f"{self.client.control_plane_url}/sessions/{self.id}/tasks/{task_id}/result"
        )
        response = await self.client.request("GET", url)
        data = response.json()
        return TaskResult(**data) if data else None

    async def get_tasks(self) -> list[TaskDefinition]:
        """Get all tasks in this session.

        Returns:
            list[TaskDefinition]: A list of task definitions in the session.
        """
        url = f"{self.client.control_plane_url}/sessions/{self.id}/tasks"
        response = await self.client.request("GET", url)
        return [TaskDefinition(**task) for task in response.json()]

    async def send_event(self, service_name: str, task_id: str, ev: Event) -> None:
        """Send event to a Workflow service.

        Args:
            service_name (str): The name of the service running the target Task.
            task_id (str): The ID of the task running the workflow receiving the event.
            ev (Event): The event to be sent to the workflow task.

        Returns:
            None
        """
        serializer = JsonSerializer()
        event_def = EventDefinition(
            event_obj_str=serializer.serialize(ev), service_id=service_name
        )

        url = f"{self.client.control_plane_url}/sessions/{self.id}/tasks/{task_id}/send_event"
        await self.client.request("POST", url, json=event_def.model_dump())

    async def send_event_def(self, task_id: str, ev_def: EventDefinition) -> None:
        """Send event to a Workflow service.

        Args:
            task_id (str): The ID of the task running the workflow receiving the event.
            ev_def (EventDefinition): The event definition describing the Event to send.

        Returns:
            None
        """
        url = f"{self.client.control_plane_url}/sessions/{self.id}/tasks/{task_id}/send_event"
        await self.client.request("POST", url, json=ev_def.model_dump())

    async def get_task_result_stream(
        self, task_id: str
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Get the result of a task in this session if it has one.

        Args:
            task_id (str): The ID of the task to get the result for.

        Returns:
            AsyncGenerator[str, None, None]: A generator that yields the result of the task.
        """
        url = f"{self.client.control_plane_url}/sessions/{self.id}/tasks/{task_id}/result_stream"
        start_time = time.time()
        while True:
            try:
                async with httpx.AsyncClient(timeout=self.client.timeout) as client:
                    async with client.stream("GET", url) as response:
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            json_line = json.loads(line)
                            yield json_line
                        break  # Exit the function if successful
            except httpx.HTTPStatusError as e:
                if e.response.status_code != 404:
                    raise  # Re-raise if it's not a 404 error
                if (
                    self.client.timeout is None  # means no timeout, always poll
                    or time.time() - start_time < self.client.timeout
                ):
                    await asyncio.sleep(self.client.poll_interval)
                else:
                    raise TimeoutError(
                        f"Task result not available after waiting for {self.client.timeout} seconds"
                    )


class SessionCollection(Collection):
    """A model representing a collection of sessions."""

    async def list(self) -> list[Session]:  # type: ignore
        """Returns a list of all the sessions in the collection."""
        sessions_url = f"{self.client.control_plane_url}/sessions"
        response = await self.client.request("GET", sessions_url)
        sessions = []
        model_class = self._prepare(Session)
        for id, session_def in response.json().items():
            sessions.append(model_class(client=self.client, id=id))
        return sessions

    async def create(self) -> Session:
        """Creates a new session and returns a Session object.

        Returns:
            Session: A Session object representing the newly created session.
        """
        return await self._create()

    async def _create(self) -> Session:
        """Async-only version of create, to be used internally from other methods."""
        create_url = f"{self.client.control_plane_url}/sessions/create"
        response = await self.client.request("POST", create_url)
        session_id = response.json()
        model_class = self._prepare(Session)
        return model_class(client=self.client, id=session_id)

    async def get(self, id: str) -> Session:
        """Gets a session by ID.

        Args:
            id (str): The ID of the session to get.

        Returns:
            Session: A Session object representing the specified session.

        Raises:
            ValueError: If the session does not exist.
        """
        return await self._get(id)

    async def _get(self, id: str) -> Session:
        """Async-only version of get, to be used internally from other methods."""

        get_url = f"{self.client.control_plane_url}/sessions/{id}"
        await self.client.request("GET", get_url)
        model_class = self._prepare(Session)
        return model_class(client=self.client, id=id)

    async def get_or_create(self, id: str) -> Session:
        """Gets a session by ID, or creates a new one if it doesn't exist.

        Returns:
            Session: A Session object representing the specified session.
        """
        try:
            return await self._get(id)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return await self._create()
            raise e

    async def delete(self, session_id: str) -> None:
        """Deletes a session by ID.

        Args:
            session_id: The ID of the session to delete.
        """
        delete_url = f"{self.client.control_plane_url}/sessions/{session_id}/delete"
        await self.client.request("POST", delete_url)


class Service(Model):
    """A model representing a Service."""

    pass


class ServiceCollection(Collection):
    async def list(self) -> list[Service]:  # type: ignore
        """Returns a list containing all the services registered with the control plane.

        Returns:
            list[Service]: List of services registered with the control plane.
        """
        services_url = f"{self.client.control_plane_url}/services"
        response = await self.client.request("GET", services_url)
        services = []
        model_class = self._prepare(Service)

        for name, service in response.json().items():
            services.append(model_class(client=self.client, id=name))

        return services

    async def register(self, service: ServiceDefinition) -> Service:
        """Registers a service with the control plane.

        Args:
            service: Definition of the Service to register.
        """
        register_url = f"{self.client.control_plane_url}/services/register"
        await self.client.request("POST", register_url, json=service.model_dump())
        model_class = self._prepare(Service)
        s = model_class(id=service.service_name, client=self.client)
        self.items[service.service_name] = s
        return s

    async def deregister(self, service_name: str) -> None:
        """Deregisters a service from the control plane.

        Args:
            service_name: The name of the Service to deregister.
        """
        deregister_url = f"{self.client.control_plane_url}/services/deregister"
        await self.client.request(
            "POST",
            deregister_url,
            params={"service_name": service_name},
        )


class Core(Model):
    @property
    def services(self) -> ServiceCollection:
        """Returns a collection containing all the services registered with the control plane.

        Returns:
            ServiceCollection: Collection of services registered with the control plane.
        """
        model_class = self._prepare(ServiceCollection)
        return model_class(client=self.client, items={})

    @property
    def sessions(self) -> SessionCollection:
        """Returns a collection to access all the sessions registered with the control plane.

        Returns:
            SessionCollection: Collection of sessions registered with the control plane.
        """
        model_class = self._prepare(SessionCollection)
        return model_class(client=self.client, items={})
