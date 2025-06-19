from pathlib import Path

import pytest

from llama_deploy.types.core import TaskDefinition


@pytest.mark.asyncio
async def test_read_env_vars_local(apiserver, client):
    here = Path(__file__).parent
    deployment_fp = here / "deployments" / "deployment_env_local.yml"
    with open(deployment_fp) as f:
        deployment = await client.apiserver.deployments.create(
            f, base_path=deployment_fp.parent
        )

    result = await deployment.tasks.run(
        TaskDefinition(service_id="test_env_workflow", input="")
    )

    assert result == "var_1: z, var_2: y, api_key: 123"
