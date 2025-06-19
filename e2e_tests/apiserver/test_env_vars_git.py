import json
from pathlib import Path

import pytest

from llama_deploy.types.core import TaskDefinition


@pytest.mark.asyncio
async def test_read_env_vars_git(apiserver, client):
    here = Path(__file__).parent
    deployment_fp = here / "deployments" / "deployment_env_git.yml"
    with open(deployment_fp) as f:
        deployment = await client.apiserver.deployments.create(
            f, base_path=deployment_fp.parent
        )

    input_str = json.dumps({"env_vars_to_read": ["VAR_1", "VAR_2", "API_KEY"]})
    result = await deployment.tasks.run(
        TaskDefinition(service_id="workflow_git", input=input_str)
    )

    assert result == "VAR_1: x, VAR_2: y, API_KEY: 123"
