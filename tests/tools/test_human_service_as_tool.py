import pytest

from llama_index.core.tools import ToolMetadata

from llama_agents.message_queues.simple import SimpleMessageQueue
from llama_agents.services.human import HumanService
from llama_agents.tools.service_as_tool import ServiceAsTool


@pytest.fixture()
def message_queue() -> SimpleMessageQueue:
    return SimpleMessageQueue()


@pytest.fixture()
def human_service(message_queue: SimpleMessageQueue) -> HumanService:
    return HumanService(
        message_queue=SimpleMessageQueue(),
        running=False,
        description="Test Human Service",
        service_name="test_human_service",
        host="https://mock-human-service.io",
        port=8000,
    )


def test_init(message_queue: SimpleMessageQueue, human_service: HumanService) -> None:
    # arrange
    tool_metadata = ToolMetadata(
        description=human_service.description,
        name=human_service.tool_name,
    )
    # act
    agent_service_tool = ServiceAsTool(
        tool_metadata=tool_metadata,
        message_queue=message_queue,
        service_name=human_service.service_name,
        timeout=5.5,
        step_interval=0.5,
    )

    # assert
    assert agent_service_tool.step_interval == 0.5
    assert agent_service_tool.message_queue == message_queue
    assert agent_service_tool.metadata == tool_metadata
    assert agent_service_tool.timeout == 5.5
    assert agent_service_tool.service_name == human_service.service_name
    assert agent_service_tool.registered is False


# def test_init_invalid_tool_name_should_raise_error(
#     message_queue: SimpleMessageQueue, agent_service: AgentService
# ) -> None:
#     # arrange
#     tool_metadata = ToolMetadata(
#         description=agent_service.description,
#         name="incorrect-name",
#     )
#     # act/assert
#     with pytest.raises(ValueError):
#         AgentServiceTool(
#             tool_metadata=tool_metadata,
#             message_queue=message_queue,
#             service_name=agent_service.service_name,
#         )


# def test_from_service_definition(
#     message_queue: SimpleMessageQueue, agent_service: AgentService
# ) -> None:
#     # arrange
#     service_def = agent_service.service_definition

#     # act
#     agent_service_tool = AgentServiceTool.from_service_definition(
#         message_queue=message_queue,
#         service_definition=service_def,
#         timeout=5.5,
#         step_interval=0.5,
#         raise_timeout=True,
#     )

#     # assert
#     assert agent_service_tool.step_interval == 0.5
#     assert agent_service_tool.message_queue == message_queue
#     assert agent_service_tool.metadata.description == service_def.description
#     assert agent_service_tool.metadata.name == f"{service_def.service_name}-as-tool"
#     assert agent_service_tool.timeout == 5.5
#     assert agent_service_tool.service_name == agent_service.service_name
#     assert agent_service_tool.raise_timeout is True
#     assert agent_service_tool.registered is False


# @pytest.mark.asyncio()
# @patch.object(ReActAgent, "arun_step")
# @patch.object(ReActAgent, "get_completed_tasks")
# async def test_tool_call_output(
#     mock_get_completed_tasks: MagicMock,
#     mock_arun_step: AsyncMock,
#     message_queue: SimpleMessageQueue,
#     agent_service: AgentService,
#     task_step_output: TaskStepOutput,
#     completed_task: Task,
# ) -> None:
#     # arrange
#     def arun_side_effect(task_id: str) -> TaskStepOutput:
#         completed_task.task_id = task_id
#         task_step_output.task_step.task_id = task_id
#         return task_step_output

#     mock_arun_step.side_effect = arun_side_effect
#     mock_get_completed_tasks.side_effect = [
#         [],
#         [],
#         [completed_task],
#         [completed_task],
#         [completed_task],
#     ]

#     agent_service_tool = AgentServiceTool.from_service_definition(
#         message_queue=message_queue,
#         service_definition=agent_service.service_definition,
#     )

#     # startup
#     await message_queue.register_consumer(agent_service.as_consumer())
#     mq_task = asyncio.create_task(message_queue.processing_loop())
#     as_task = asyncio.create_task(agent_service.processing_loop())

#     # act
#     tool_output = await agent_service_tool.acall(input="What is the secret fact?")

#     # clean-up/shutdown
#     await asyncio.sleep(0.1)
#     mq_task.cancel()
#     as_task.cancel()

#     # assert
#     assert tool_output.content == "A baby llama is called a 'Cria'."
#     assert tool_output.tool_name == agent_service_tool.metadata.name
#     assert tool_output.raw_input == {
#         "args": (),
#         "kwargs": {"input": "What is the secret fact?"},
#     }
#     assert len(agent_service_tool.tool_call_results) == 0
#     assert agent_service_tool.registered is True


# @pytest.mark.asyncio()
# @patch.object(ReActAgent, "arun_step")
# @patch.object(ReActAgent, "get_completed_tasks")
# async def test_tool_call_raises_timeout_error(
#     mock_get_completed_tasks: MagicMock,
#     mock_arun_step: AsyncMock,
#     message_queue: SimpleMessageQueue,
#     agent_service: AgentService,
#     task_step_output: TaskStepOutput,
#     completed_task: Task,
# ) -> None:
#     # arrange
#     def arun_side_effect(task_id: str) -> TaskStepOutput:
#         completed_task.task_id = task_id
#         task_step_output.task_step.task_id = task_id
#         return task_step_output

#     mock_arun_step.side_effect = arun_side_effect
#     mock_get_completed_tasks.side_effect = [
#         [],
#         [],
#         [completed_task],
#         [completed_task],
#         [completed_task],
#     ]

#     agent_service_tool = AgentServiceTool.from_service_definition(
#         message_queue=message_queue,
#         service_definition=agent_service.service_definition,
#         timeout=1e-12,
#         raise_timeout=True,
#     )

#     # startup
#     await message_queue.register_consumer(agent_service.as_consumer())
#     mq_task = asyncio.create_task(message_queue.processing_loop())
#     as_task = asyncio.create_task(agent_service.processing_loop())

#     # act/assert
#     with pytest.raises(
#         (TimeoutError, asyncio.TimeoutError, asyncio.exceptions.TimeoutError)
#     ):
#         await agent_service_tool.acall(input="What is the secret fact?")

#     # clean-up/shutdown
#     mq_task.cancel()
#     as_task.cancel()


# @pytest.mark.asyncio()
# @patch.object(ReActAgent, "arun_step")
# @patch.object(ReActAgent, "get_completed_tasks")
# async def test_tool_call_hits_timeout_but_returns_tool_output(
#     mock_get_completed_tasks: MagicMock,
#     mock_arun_step: AsyncMock,
#     message_queue: SimpleMessageQueue,
#     agent_service: AgentService,
#     task_step_output: TaskStepOutput,
#     completed_task: Task,
# ) -> None:
#     # arrange
#     def arun_side_effect(task_id: str) -> TaskStepOutput:
#         completed_task.task_id = task_id
#         task_step_output.task_step.task_id = task_id
#         return task_step_output

#     mock_arun_step.side_effect = arun_side_effect
#     mock_get_completed_tasks.side_effect = [
#         [],
#         [],
#         [completed_task],
#         [completed_task],
#         [completed_task],
#     ]

#     agent_service_tool = AgentServiceTool.from_service_definition(
#         message_queue=message_queue,
#         service_definition=agent_service.service_definition,
#         timeout=1e-12,
#         raise_timeout=False,
#     )

#     # startup
#     await message_queue.register_consumer(agent_service.as_consumer())
#     mq_task = asyncio.create_task(message_queue.processing_loop())
#     as_task = asyncio.create_task(agent_service.processing_loop())

#     # act/assert
#     tool_output = await agent_service_tool.acall(input="What is the secret fact?")

#     # clean-up/shutdown
#     mq_task.cancel()
#     as_task.cancel()

#     assert "Encountered error" in tool_output.content
#     assert tool_output.is_error
#     assert tool_output.tool_name == agent_service_tool.metadata.name
#     assert tool_output.raw_input == {
#         "args": (),
#         "kwargs": {"input": "What is the secret fact?"},
#     }
#     assert len(agent_service_tool.tool_call_results) == 0
#     assert agent_service_tool.registered is True
