import json
from typing import Any, Dict

from llama_index.core.query_pipeline import CustomQueryComponent

from llama_agents.types import ServiceDefinition


class ServiceComponent(CustomQueryComponent):
    name: str
    description: str

    @classmethod
    def from_service_definition(
        cls, service_def: ServiceDefinition
    ) -> "ServiceComponent":
        return cls(name=service_def.service_name, description=service_def.description)

    @property
    def _input_keys(self) -> set:
        """Input keys dict."""
        return {"input"}

    @property
    def _output_keys(self) -> set:
        return {"service_output"}

    def _run_component(self, **kwargs: Any) -> Dict[str, Any]:
        """Return a dummy output."""
        json_dump = json.dumps(
            {
                "name": self.name,
                "description": self.description,
                **kwargs,
            }
        )
        return {"service_output": json_dump}

    async def _arun_component(self, **kwargs: Any) -> Dict[str, Any]:
        """Return a dummy output."""
        json_dump = json.dumps(
            {
                "name": self.name,
                "description": self.description,
                **kwargs,
            }
        )
        return {"service_output": json_dump}
