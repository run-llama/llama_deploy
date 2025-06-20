import json
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from mcp.server.fastmcp import FastMCP

from llama_index.core.workflow import StartEvent, StopEvent
from workflows import Workflow

from llama_deploy.apiserver.server import manager


@asynccontextmanager
async def lifespan(app: FastMCP) -> AsyncIterator[None]:
    deployments = list(manager._deployments.values())
    services: list[tuple[str, Workflow]] = [
        (workflow_name, workflow)
        for deployment in deployments
        for workflow_name, workflow in deployment._workflow_services.items()
    ]

    for workflow_name, workflow in services:
        start: type[StartEvent] = workflow._start_event_class
        stop: type[StopEvent] = workflow._stop_event_class

        def make_tool(workflow: Workflow, start: type[StartEvent]) -> Any:
            async def tool(event: dict[str, Any]) -> dict[str, Any]:
                handler = workflow.run(start_event=start.model_validate(event))
                result = await handler
                return result.model_dump()

            tool.__name__ = workflow_name

            return tool

        tool = make_tool(workflow, start)
        description = workflow.__class__.__doc__ or ""
        description += "\n\nInput:\n" + json.dumps(start.model_json_schema(), indent=2)
        description += "\n\nOutput:\n" + json.dumps(stop.model_json_schema(), indent=2)
        app.add_tool(tool, workflow_name, description=description)

    yield None


mcp_app: FastMCP = FastMCP(lifespan=lifespan, stateless_http=True, json_response=True)
