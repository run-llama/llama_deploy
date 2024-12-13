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


workflow = MyWorkflow(settings=WorkflowSettings())


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
