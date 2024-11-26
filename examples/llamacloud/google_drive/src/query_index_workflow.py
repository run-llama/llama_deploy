import asyncio
import argparse
from dataclasses import dataclass

import nest_asyncio
from llama_index.core.workflow import Workflow, StartEvent, StopEvent, Event, step
from llama_index.indices.managed.llama_cloud import LlamaCloudIndex

# Apply nest_asyncio at the start
nest_asyncio.apply()


@dataclass
class LlamaCloudConfig:
    """Configuration class for LlamaCloud settings"""

    project_name: str
    index_name: str
    organization_id: str
    query: str


class QueryIndexEvent(Event):
    """Event for querying the index"""

    pass


class LlamaCloudQueryWorkflow(Workflow):
    """Workflow for creating and querying a LlamaCloud index"""

    def __init__(self, config: LlamaCloudConfig):
        super().__init__()
        self.config = config

    @step
    async def create_index(self, ev: StartEvent) -> QueryIndexEvent:
        """Create LlamaCloud index"""
        index = LlamaCloudIndex(
            name=self.config.index_name,
            project_name=self.config.project_name,
            organization_id=self.config.organization_id,
        )
        return QueryIndexEvent(index=index)

    @step
    async def query_index(self, ev: QueryIndexEvent) -> StopEvent:
        """Query the created index"""
        index = ev.get("index")
        query_engine = index.as_query_engine()
        response = query_engine.query(self.config.query)
        return StopEvent(result=str(response))


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="LlamaCloud Index Query Tool")

    parser.add_argument(
        "--project-name", default="Default", help="Name of the LlamaCloud project"
    )
    parser.add_argument(
        "--index-name", required=True, help="Name of the index to query"
    )
    parser.add_argument(
        "--organization-id", required=True, help="LlamaCloud organization ID"
    )
    parser.add_argument("--query", required=True, help="Query to run against the index")

    return parser.parse_args()


async def main():
    try:
        # Parse command line arguments
        args = parse_arguments()

        # Create configuration with API key from environment
        config = LlamaCloudConfig(
            project_name=args.project_name,
            index_name=args.index_name,
            organization_id=args.organization_id,
            query=args.query,
        )

        # Create and run workflow
        workflow = LlamaCloudQueryWorkflow(config)
        result = await workflow.run()

        # print query
        print("\nQuery:")
        print("-" * 50)
        print(config.query)
        print("-" * 50)
        # Print the query result
        print("\nAnswer:")
        print("-" * 50)
        print(result)
        print("-" * 50)

    except ValueError as e:
        print(f"Configuration error: {str(e)}")
        exit(1)
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())
