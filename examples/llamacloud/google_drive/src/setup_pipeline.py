import json
import asyncio
import argparse
from dataclasses import dataclass
from typing import Dict, Any
from pathlib import Path

from llama_cloud.client import LlamaCloud
from llama_cloud.types import (
    CloudGoogleDriveDataSource,
    ConfigurableDataSourceNames,
    DataSourceCreate,
)
from llama_index.core.workflow import (
    Event,
    StartEvent,
    StopEvent,
    Workflow,
    step,
)

import os


@dataclass
class PipelineConfig:
    """Configuration class for pipeline settings"""

    data_source_name: str
    folder_id: str
    pipeline_name: str
    service_account_key_path: Path
    chunk_size: int = 1024
    chunk_overlap: int = 20


def load_service_account_key(file_path: Path) -> Dict[str, Any]:
    """Load Google service account key from JSON file"""
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        raise ValueError(
            f"Error loading service account key from {file_path}: {str(e)}"
        )


def create_data_source(client: LlamaCloud, config: PipelineConfig) -> Any:
    """Create a Google Drive data source"""
    service_account_key = load_service_account_key(config.service_account_key_path)

    ds = DataSourceCreate(
        name=config.data_source_name,
        source_type=ConfigurableDataSourceNames.GOOGLE_DRIVE,
        component=CloudGoogleDriveDataSource(
            folder_id=config.folder_id,
            service_account_key=service_account_key,
        ),
    )
    return client.data_sources.create_data_source(request=ds)


def setup_pipeline(
    client: LlamaCloud, data_source_id: str, config: PipelineConfig
) -> Any:
    """Setup the LlamaCloud pipeline with the specified configuration"""
    embedding_config = {
        "type": "OPENAI_EMBEDDING",
        "component": {
            "api_key": os.environ["OPENAI_API_KEY"],
            "model_name": "text-embedding-ada-002",
        },
    }

    transform_config = {
        "mode": "auto",
        "config": {
            "chunk_size": config.chunk_size,
            "chunk_overlap": config.chunk_overlap,
        },
    }

    pipeline_config = {
        "name": config.pipeline_name,
        "embedding_config": embedding_config,
        "transform_config": transform_config,
        "data_sink_id": None,
    }

    pipeline = client.pipelines.upsert_pipeline(request=pipeline_config)
    client.pipelines.add_data_sources_to_pipeline(
        pipeline.id,
        request=[{"data_source_id": data_source_id, "sync_interval": 43200.0}],
    )
    return pipeline


class CreateDataSourceEvent(Event):
    pass


class SetupPipelineEvent(Event):
    pass


class SetupLlamaCloudPipelineFlow(Workflow):
    def __init__(self, config: PipelineConfig):
        super().__init__()
        self.config = config

    @step
    async def setup_client(self, ev: StartEvent) -> CreateDataSourceEvent:
        client = LlamaCloud(token=os.environ["LLAMA_CLOUD_API_KEY"])
        return CreateDataSourceEvent(client=client)

    @step
    async def create_data_source(self, ev: CreateDataSourceEvent) -> SetupPipelineEvent:
        data_source = create_data_source(ev.client, self.config)
        return SetupPipelineEvent(client=ev.client, data_source=data_source)

    @step
    async def setup_pipeline(self, ev: SetupPipelineEvent) -> StopEvent:
        pipeline = setup_pipeline(ev.client, ev.data_source.id, self.config)
        return StopEvent(result=pipeline)


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Setup LlamaCloud Pipeline")
    parser.add_argument(
        "--data-source-name", required=True, help="Name of the data source"
    )
    parser.add_argument("--folder-id", required=True, help="Google Drive folder ID")
    parser.add_argument("--pipeline-name", required=True, help="Name of the pipeline")
    parser.add_argument(
        "--service-account-key",
        required=True,
        type=Path,
        help="Path to Google service account key JSON file",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1024,
        help="Chunk size for document processing (default: 1024)",
    )
    parser.add_argument(
        "--chunk-overlap", type=int, default=20, help="Chunk overlap size (default: 20)"
    )

    return parser.parse_args()


async def main():
    args = parse_arguments()

    config = PipelineConfig(
        data_source_name=args.data_source_name,
        folder_id=args.folder_id,
        pipeline_name=args.pipeline_name,
        service_account_key_path=args.service_account_key,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )

    workflow = SetupLlamaCloudPipelineFlow(config)
    _ = await workflow.run()
    print("Pipeline setup completed successfully")


if __name__ == "__main__":
    asyncio.run(main())
