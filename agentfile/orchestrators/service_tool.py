from llama_index.core.tools import AsyncBaseTool, ToolMetadata

from agentfile.types import ServiceDefinition


class ServiceTool(AsyncBaseTool):
    def __init__(self, service_def: ServiceDefinition) -> None:
        self.name = service_def.service_name
        self.description = service_def.description

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name=self.name,
            description=self.description,
            return_direct=True,
        )

    def call(self, input: str) -> str:
        return f'{"name": {self.name}, "description": {self.description}, "input": {input}}'

    async def acall(self, input: str) -> str:
        return f'{"name": {self.name}, "description": {self.description}, "input": {input}}'
