from llama_index.core.tools import AsyncBaseTool, ToolMetadata, ToolOutput

from llama_deploy.types import ServiceDefinition


class ServiceTool(AsyncBaseTool):
    """A tool that wraps a service.

    Mostly used under the hood by the agent orchestrator.

    Attributes:
        name (str):
            The name of the tool.
        description (str):
            The description of the tool.
    """

    def __init__(self, name: str, description: str) -> None:
        self.name = name
        self.description = description

    @classmethod
    def from_service_definition(cls, service_def: ServiceDefinition) -> "ServiceTool":
        return cls(service_def.service_name, service_def.description)

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name=self.name,
            description=self.description,
        )

    def _make_dummy_output(self, input: str) -> ToolOutput:
        return ToolOutput(
            content=input,
            tool_name=self.name,
            raw_input={"input": input},
            raw_output=input,
        )

    def call(self, input: str) -> ToolOutput:
        return self._make_dummy_output(input)

    async def acall(self, input: str) -> ToolOutput:
        return self._make_dummy_output(input)
