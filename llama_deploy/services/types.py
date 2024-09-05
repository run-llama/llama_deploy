from pydantic import BaseModel
from typing import Dict, List, Optional

from llama_index.core.agent.types import TaskStep, TaskStepOutput, Task
from llama_index.core.agent.runner.base import AgentState, TaskState

from llama_deploy.types import ChatMessage

# ------ FastAPI types ------


class _Task(BaseModel):
    task_id: str
    input: Optional[str]
    extra_state: dict

    @classmethod
    def from_task(cls, task: Task) -> "_Task":
        _extra_state = {}
        for key, value in task.extra_state.items():
            _extra_state[key] = str(value)

        return cls(task_id=task.task_id, input=task.input, extra_state=_extra_state)


class _TaskStep(BaseModel):
    task_id: str
    step_id: str
    input: Optional[str]
    step_state: dict
    prev_steps: List["_TaskStep"]
    next_steps: List["_TaskStep"]
    is_ready: bool

    @classmethod
    def from_task_step(cls, task_step: TaskStep) -> "_TaskStep":
        _step_state = {}
        for key, value in task_step.step_state.items():
            _step_state[key] = str(value)

        return cls(
            task_id=task_step.task_id,
            step_id=task_step.step_id,
            input=task_step.input,
            step_state=_step_state,
            prev_steps=[
                cls.from_task_step(prev_step) for prev_step in task_step.prev_steps
            ],
            next_steps=[
                cls.from_task_step(next_step) for next_step in task_step.next_steps
            ],
            is_ready=task_step.is_ready,
        )


class _TaskStepOutput(BaseModel):
    output: str
    task_step: _TaskStep
    next_steps: List[_TaskStep]
    is_last: bool

    @classmethod
    def from_task_step_output(cls, step_output: TaskStepOutput) -> "_TaskStepOutput":
        return cls(
            output=str(step_output.output),
            task_step=_TaskStep.from_task_step(step_output.task_step),
            next_steps=[
                _TaskStep.from_task_step(next_step)
                for next_step in step_output.next_steps
            ],
            is_last=step_output.is_last,
        )


class _TaskSate(BaseModel):
    task: _Task
    step_queue: List[_TaskStep]
    completed_steps: List[_TaskStepOutput]

    @classmethod
    def from_task_state(cls, task_state: TaskState) -> "_TaskSate":
        return cls(
            task=_Task.from_task(task_state.task),
            step_queue=[
                _TaskStep.from_task_step(step) for step in list(task_state.step_queue)
            ],
            completed_steps=[
                _TaskStepOutput.from_task_step_output(step)
                for step in task_state.completed_steps
            ],
        )


class _AgentState(BaseModel):
    task_dict: Dict[str, _TaskSate]

    @classmethod
    def from_agent_state(cls, agent_state: AgentState) -> "_AgentState":
        return cls(
            task_dict={
                task_id: _TaskSate.from_task_state(task_state)
                for task_id, task_state in agent_state.task_dict.items()
            }
        )


class _ChatMessage(BaseModel):
    content: str
    role: str
    additional_kwargs: dict

    @classmethod
    def from_chat_message(cls, chat_message: ChatMessage) -> "_ChatMessage":
        return cls(
            content=str(chat_message.content),
            role=str(chat_message.role),
            additional_kwargs=chat_message.additional_kwargs,
        )
