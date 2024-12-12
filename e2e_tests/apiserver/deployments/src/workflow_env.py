import asyncio

from llama_index.core.workflow import (
    Context,
    StartEvent,
    StopEvent,
    Workflow,
    step,
)
from llama_index.core.bridge.pydantic_settings import BaseSettings
from llama_index.core.bridge.pydantic import Field, SecretStr


class WorkflowSettings(BaseSettings):
    var_1: str | None = Field(None)
    var_2: str | None = Field(None)
    api_key: SecretStr = ""


class MyWorkflow(Workflow):
    def __init__(self, settings: WorkflowSettings, **kwargs) -> None:
        super().__init__(**kwargs)
        self.settings = settings
        print(f"{settings.model_dump()}")

    @step()
    async def run_step(self, ctx: Context, ev: StartEvent) -> StopEvent:
        return StopEvent(
            # result depends on variables read from environment
            result=(
                f"var_1: {self.settings.var_1}, "
                f"var_2: {self.settings.var_2}, "
                f"api_key: {self.settings.api_key.get_secret_value()}"
            )
        )


# env prefix is f"{service_id}_"
workflow = MyWorkflow(
    settings=WorkflowSettings(_env_prefix="test_env_workflow_".upper())
)

another_workflow = MyWorkflow(
    settings=WorkflowSettings(_env_prefix="another_workflow_".upper())
)


async def main(w: Workflow):
    h = w.run()
    print(await h)


if __name__ == "__main__":
    import os

    # set env variables
    os.environ["VAR_1"] = "x"
    os.environ["API_KEY"] = "123"

    w = MyWorkflow(settings=WorkflowSettings())

    asyncio.run(main(w))
