import asyncio
from pathlib import Path
import yaml
from dataclasses import dataclass

import nest_asyncio
from llama_index.core.workflow import Workflow, StartEvent, StopEvent, step
from llama_index.indices.managed.llama_cloud import LlamaCloudIndex

# Apply nest_asyncio at the start
nest_asyncio.apply()


@dataclass
class LlamaCloudConfig:
    """Configuration class for LlamaCloud settings"""

    index_name: str
    project_name: str
    organization_id: str

    @classmethod
    def from_yaml(cls, config_path: str = "src/config.yml") -> "LlamaCloudConfig":
        """Load configuration from YAML file"""
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        llamacloud_config = config.get("llamacloud", {})
        return cls(
            index_name=llamacloud_config.get("index_name"),
            project_name=llamacloud_config.get("project_name"),
            organization_id=llamacloud_config.get("organization_id"),
        )


class LlamaCloudQueryWorkflow(Workflow):
    """Workflow for creating and querying a LlamaCloud index"""

    def __init__(self, config: LlamaCloudConfig):
        super().__init__()
        self.config = config

    @step
    async def query_index(self, ev: StartEvent) -> StopEvent:
        """Query the created index"""
        index = LlamaCloudIndex(
            name=self.config.index_name,
            project_name=self.config.project_name,
            organization_id=self.config.organization_id,
        )
        query = ev.get("query")
        query_engine = index.as_query_engine()
        response = query_engine.query(query)
        return StopEvent(result={"query": query, "response": str(response)})


# Load configuration from YAML file
config = LlamaCloudConfig.from_yaml()

# Create workflow with configuration
llamacloud_workflow = LlamaCloudQueryWorkflow(config)


async def main():
    try:
        # Run workflow
        result = await llamacloud_workflow.run(
            query="Hello. What information do you have?"
        )

        # Print results
        print("\nQuery:")
        print("-" * 50)
        print(result["query"])
        print("-" * 50)
        print("\nAnswer:")
        print("-" * 50)
        print(result["response"])
        print("-" * 50)

    except FileNotFoundError as e:
        print(f"Configuration error: {str(e)}")
        exit(1)
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())
