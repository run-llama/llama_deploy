import json
from typing import Any, Dict, Optional

from llama_index.core.bridge.pydantic import PrivateAttr
from llama_index.core.query_pipeline import CustomQueryComponent
from llama_index.core.base.query_pipeline.query import InputKeys

from llama_deploy.types import ServiceDefinition
from enum import Enum


class ModuleType(str, Enum):
    """Module types.

    Can be either an agent or a component.

    NOTE: this is to allow both agent services and component services to be stitched together with
    the pipeline orchestrator.

    Ideally there should not be more types.

    """

    AGENT = "agent"
    COMPONENT = "component"


class ServiceComponent(CustomQueryComponent):
    """Service component.

    This wraps a service into a component that can be used in a query pipeline.

    Attributes:
        name (str): The name of the service.
        description (str): The description of the service.
        input_keys (Optional[InputKeys]): The input keys. Defaults to a single `input` key.
        module_type (ModuleType): The module type. Defaults to `ModuleType.AGENT`.

    Examples:
        ```python
        from llama_deploy import ServiceComponent, AgentService

        rag_agent_server = AgentService(
            agent=rag_agent,
            message_queue=message_queue,
            description="rag_agent",
        )
        rag_agent_server_c = ServiceComponent.from_service_definition(
            rag_agent_server.service_definition
        )

        pipeline = QueryPipeline(chain=[rag_agent_server_c])
        ```
    """

    name: str
    description: str

    # Store a set of input keys from upstream modules
    # NOTE: no need to track the output keys, this is a fake module anyways
    _cur_input_keys: InputKeys = PrivateAttr()

    module_type: ModuleType = ModuleType.AGENT

    def __init__(
        self,
        name: str,
        description: str,
        input_keys: Optional[InputKeys] = None,
        module_type: ModuleType = ModuleType.AGENT,
    ) -> None:
        super().__init__(name=name, description=description, module_type=module_type)
        self._cur_input_keys = input_keys or InputKeys.from_keys({"input"})

    @classmethod
    def from_service_definition(
        cls,
        service_def: ServiceDefinition,
        input_keys: Optional[InputKeys] = None,
        module_type: ModuleType = ModuleType.AGENT,
    ) -> "ServiceComponent":
        """Create a service component from a service definition."""
        return cls(
            name=service_def.service_name,
            description=service_def.description,
            input_keys=input_keys,
            module_type=module_type,
        )

    @classmethod
    def from_component_service(
        cls,
        component_service: Any,
    ) -> "ServiceComponent":
        """Create a service component from a component service."""
        from llama_deploy.services.component import ComponentService

        if not isinstance(component_service, ComponentService):
            raise ValueError("component_service must be a Component")

        component = component_service.component
        return cls.from_service_definition(
            component_service.service_definition,
            input_keys=component.input_keys,
            module_type=ModuleType.COMPONENT,
        )

    @property
    def input_keys(self) -> InputKeys:
        """Input keys."""
        # NOTE: user can override this too, but we have them implement an
        # abstract method to make sure they do it

        return self._cur_input_keys

    @property
    def _input_keys(self) -> set:
        """Input keys dict."""
        # HACK: not used
        return set()

    @property
    def _output_keys(self) -> set:
        return {"service_output"}

    def _run_component(self, **kwargs: Any) -> Dict[str, Any]:
        """Return a dummy output."""
        json_dump = json.dumps(
            {
                "name": self.name,
                "description": self.description,
                "input": kwargs,
            }
        )
        return {"service_output": json_dump}

    async def _arun_component(self, **kwargs: Any) -> Dict[str, Any]:
        """Return a dummy output."""
        json_dump = json.dumps(
            {
                "name": self.name,
                "description": self.description,
                "input": kwargs,
            }
        )
        return {"service_output": json_dump}
