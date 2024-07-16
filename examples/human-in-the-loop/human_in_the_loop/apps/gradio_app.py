"""Gradio app."""

from enum import Enum
from dataclasses import dataclass, field
from io import StringIO
from typing import Any, Dict, List, Optional, Tuple
import asyncio
import gradio as gr
import sys

from llama_agents import LlamaAgentsClient, CallableMessageConsumer, QueueMessage
from llama_agents.types import ActionTypes, TaskResult
from human_in_the_loop.apps.css import css

import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class Capturing(list):
    """To capture the stdout from `BaseAgent.stream_chat` with `verbose=True`. Taken from
    https://stackoverflow.com/questions/16571150/\
        how-to-capture-stdout-output-from-a-python-function-call.
    """

    def __enter__(self) -> Any:
        self._stdout = sys.stdout
        sys.stdout = self._stringio = StringIO()
        return self

    def __exit__(self, *args) -> None:
        self.extend(self._stringio.getvalue().splitlines())
        del self._stringio  # free up some memory
        sys.stdout = self._stdout


class TaskStatus(str, Enum):
    HUMAN_REQUIRED = "human_required"
    COMPLETED = "completed"
    SUBMITTED = "submitted"


@dataclass
class TaskModel:
    task_id: str
    input: str
    status: TaskStatus
    prompt: Optional[str] = None
    chat_history: List[gr.ChatMessage] = field(default_factory=list)


class HumanInTheLoopGradioApp:
    """Human In The Loop Gradio App."""

    def __init__(
        self,
        human_in_loop_queue: asyncio.Queue,
        human_in_loop_result_queue: asyncio.Queue,
        control_plane_host: str = "127.0.0.1",
        control_plane_port: Optional[int] = 8000,
    ) -> None:
        self.human_in_loop_queue = human_in_loop_queue
        self.human_in_loop_result_queue = human_in_loop_result_queue
        self.app = gr.Blocks(css=css)
        self._client = LlamaAgentsClient(
            control_plane_url=(
                f"http://{control_plane_host}:{control_plane_port}"
                if control_plane_port
                else f"http://{control_plane_host}"
            )
        )
        self._step_interval = 0.5
        self._timeout = 60
        self._raise_timeout = False
        self._human_in_the_loop_task: Optional[str] = None
        self._human_input: Optional[str] = None
        self._final_task_consumer = CallableMessageConsumer(
            message_type="human", handler=self.process_completed_task_messages
        )
        self._completed_tasks_queue = asyncio.Queue()

        with self.app:
            submitted_tasks_state = gr.State([])
            human_required_tasks_state = gr.State([])
            completed_tasks_state = gr.State([])
            current_task = gr.State(None)

            with gr.Row():
                gr.Markdown("# Human In The Loop")
            with gr.Row():
                chat_window = gr.Chatbot(
                    type="messages",
                    label="Message History",
                    scale=3,
                )
                console = gr.HTML(elem_id="box")
            with gr.Row():
                message = gr.Textbox(label="Write A Message", scale=4)
                clear = gr.ClearButton()

            timer = gr.Timer(2)
            completed_timer = gr.Timer(5)

            # event listeners
            # message submit
            message.submit(
                self._handle_user_message,
                [
                    message,
                    current_task,
                    submitted_tasks_state,
                    human_required_tasks_state,
                    completed_tasks_state,
                ],
                [
                    message,
                    current_task,
                    submitted_tasks_state,
                    human_required_tasks_state,
                    completed_tasks_state,
                    chat_window,
                ],
            )

            # current task
            current_task.change(
                self._current_task_change_handler,
                [
                    current_task,
                    submitted_tasks_state,
                    human_required_tasks_state,
                    completed_tasks_state,
                ],
                chat_window,
            )

            # tick
            timer.tick(
                self._tick_handler,
                [
                    submitted_tasks_state,
                    human_required_tasks_state,
                    completed_tasks_state,
                    current_task,
                ],
                [
                    submitted_tasks_state,
                    human_required_tasks_state,
                    completed_tasks_state,
                    current_task,
                ],
            )

            # tick
            completed_timer.tick(
                self._check_for_completed_tasks_tick_handler,
                [
                    submitted_tasks_state,
                    human_required_tasks_state,
                    completed_tasks_state,
                    current_task,
                ],
                [
                    submitted_tasks_state,
                    human_required_tasks_state,
                    completed_tasks_state,
                    current_task,
                ],
            )

            # clear chat
            clear.click(self._reset_chat, None, [message, chat_window, current_task])

            @gr.render(
                inputs=[
                    submitted_tasks_state,
                    human_required_tasks_state,
                    completed_tasks_state,
                ]
            )
            def render_datasets(submitted, human_needed, completed):
                human_needed_sample = [[t.input] for t in human_needed]
                submitted_sample = [[t.input] for t in submitted]
                completed_sample = [[t.input] for t in completed]

                with gr.Row():
                    with gr.Column():

                        async def _handle_selection_submitted(
                            values: List[str],
                            evt: gr.SelectData,
                        ):
                            logger.info(
                                f"You selected {evt.value} at {evt.index} from {evt.target}"
                            )
                            task: TaskModel = submitted[evt.index]
                            logger.info(f"selected task: {task}")
                            return task.chat_history, (evt.index, task.status)

                        markdown = gr.Markdown(visible=False)
                        submitted_tasks_dataset = gr.Dataset(
                            samples=submitted_sample,
                            components=[markdown],
                            label="Submitted",
                        )
                        submitted_tasks_dataset.select(
                            _handle_selection_submitted,
                            [submitted_tasks_dataset],
                            [chat_window, current_task],
                        )
                    with gr.Column():

                        async def _handle_selection_human(
                            values: List[str],
                            evt: gr.SelectData,
                        ):
                            logger.info(
                                f"You selected {evt.value} at {evt.index} from {evt.target}"
                            )
                            task: TaskModel = human_needed[evt.index]
                            logger.info(f"selected task: {task}")
                            return task.chat_history, (evt.index, task.status)

                        markdown = gr.Markdown(visible=False)
                        human_input_required_dataset = gr.Dataset(
                            components=[markdown],
                            samples=human_needed_sample,
                            label="Human Input Required",
                            elem_classes="human-needed",
                        )
                        human_input_required_dataset.select(
                            _handle_selection_human,
                            [human_input_required_dataset],
                            [chat_window, current_task],
                        )
                    with gr.Column():

                        async def _handle_selection_completed(
                            values: List[str],
                            evt: gr.SelectData,
                        ):
                            logger.info(
                                f"You selected {evt.value} at {evt.index} from {evt.target}"
                            )
                            task: TaskModel = completed[evt.index]
                            logger.info(f"selected task: {task}")
                            return task.chat_history, (evt.index, task.status)

                        markdown = gr.Markdown(visible=False)
                        completed_tasks_dataset = gr.Dataset(
                            components=[markdown],
                            samples=completed_sample,
                            label="Completed Tasks",
                            elem_classes="completed-tasks",
                        )
                        completed_tasks_dataset.select(
                            _handle_selection_completed,
                            [completed_tasks_dataset],
                            [chat_window, current_task],
                        )

    async def process_completed_task_messages(self, message: QueueMessage, **kwargs):
        if message.action == ActionTypes.COMPLETED_TASK:
            task_res = TaskResult(**message.data)
            await self._completed_tasks_queue.put(task_res)
            logger.info(f"Added task result to queue")

    async def _current_task_change_handler(
        self,
        current_task: Optional[Tuple[int, str]],
        submitted: List[TaskModel],
        human_needed: List[TaskModel],
        completed: List[TaskModel],
    ):
        if current_task:
            ix, status = current_task
            if status == TaskStatus.SUBMITTED:
                task = submitted[ix]
            elif status == TaskStatus.HUMAN_REQUIRED:
                task = human_needed[ix]
            else:
                task = completed[ix]
            return task.chat_history
        return []

    async def _check_for_completed_tasks_tick_handler(
        self,
        submitted: List[TaskModel],
        human_needed: List[TaskModel],
        completed: List[TaskModel],
        current_task: Tuple[int, str],
    ) -> List[TaskModel]:
        try:
            task_res: TaskResult = self._completed_tasks_queue.get_nowait()
            if task_res.task_id in [t.task_id for t in submitted]:
                ix, task = next(
                    (ix, t)
                    for ix, t in enumerate(submitted)
                    if t.task_id == task_res.task_id
                )
                task.status = TaskStatus.COMPLETED
                task.chat_history.append(
                    gr.ChatMessage(role="assistant", content=task_res.result)
                )
                del submitted[ix]
                completed.append(task)

                current_task_ix, current_task_status = current_task
                if (
                    current_task_status == TaskStatus.SUBMITTED
                    and current_task_ix == ix
                ):
                    current_task = (len(completed) - 1, TaskStatus.COMPLETED)

            elif task_res.task_id in [t.task_id for t in human_needed]:
                ix, task = next(
                    (ix, t)
                    for ix, t in enumerate(human_needed)
                    if t.task_id == task_res.task_id
                )
                task.status = TaskStatus.COMPLETED
                task.chat_history.append(
                    gr.ChatMessage(role="assistant", content=task_res.result)
                )
                del human_needed[ix]
                completed.append(task)

                current_task_ix, current_task_status = current_task
                if (
                    current_task_status == TaskStatus.HUMAN_REQUIRED
                    and current_task_ix == ix
                ):
                    current_task = (len(completed) - 1, TaskStatus.COMPLETED)
            else:
                raise ValueError(
                    "Completed task not in submitted or human_needed lists."
                )
        except asyncio.QueueEmpty:
            pass

        return submitted, human_needed, completed, current_task

    async def _tick_handler(
        self,
        submitted: List[TaskModel],
        human_needed: List[TaskModel],
        completed: List[TaskModel],
        current_task: Tuple[int, str],
    ) -> str:
        try:
            dict: Dict[str, str] = self.human_in_loop_queue.get_nowait()
            prompt = dict.get("prompt")
            task_id = dict.get("task_id")
            logger.info(f"prompt: {prompt}, task_id: {task_id}")

            # find task with the provided task_id
            try:
                ix, task = next(
                    (ix, t)
                    for ix, t in enumerate(submitted)
                    if t.input.lower() == prompt.lower()
                )
                task.prompt = prompt
                task.status = TaskStatus.HUMAN_REQUIRED
                task.chat_history += [
                    gr.ChatMessage(
                        role="assistant",
                        content="Human assistance is required.",
                        metadata={"title": "🪵 System message"},
                    ),
                    gr.ChatMessage(role="assistant", content=prompt),
                ]

                del submitted[ix]
                human_needed.append(task)

                current_task_ix, current_task_status = current_task
                if (
                    current_task_status == TaskStatus.SUBMITTED
                    and current_task_ix == ix
                ):
                    current_task = (len(human_needed) - 1, TaskStatus.HUMAN_REQUIRED)

            except StopIteration:
                raise ValueError("Cannot find task in list of tasks.")
            logger.info("appended human input request.")
        except asyncio.QueueEmpty:
            logger.info("human input request queue is empty.")
            pass

        return submitted, human_needed, completed, current_task

    async def _handle_user_message(
        self,
        user_message: str,
        current_task: Optional[Tuple[int, str]],
        submitted: List[TaskModel],
        human_needed: List[TaskModel],
        completed: List[TaskModel],
    ):
        """Handle the user submitted message. Clear message box, and append
        to the history.
        """
        message = gr.ChatMessage(role="user", content=user_message)
        if current_task:
            # find current task from tasks
            # append message to associated chat history
            # chat_history.append(message)
            # submit human input fn
            ix, status = current_task
            if status == TaskStatus.SUBMITTED:
                task = submitted[ix]
            elif status == TaskStatus.HUMAN_REQUIRED:
                task = human_needed[ix]
                task.chat_history.append(message)
                human_needed[ix] = task
                await self.human_in_loop_result_queue.put(user_message)
            else:
                task = completed[ix]
        else:
            # create new task and store in state
            task_id = self._client.create_task(user_message)
            task = TaskModel(
                task_id=task_id,
                input=user_message,
                chat_history=[
                    message,
                    gr.ChatMessage(
                        role="assistant",
                        content=f"Successfully submitted task: {task_id}.",
                        metadata={"title": "🪵 System message"},
                    ),
                ],
                status=TaskStatus.SUBMITTED,
            )
            submitted.append(task)
            current_task = (len(submitted) - 1, TaskStatus.SUBMITTED)

        return "", current_task, submitted, human_needed, completed, task.chat_history

    async def _poll_for_task_result(self, task_id: str):
        task_result = None
        while task_result is None:
            if not self.human_in_loop_queue.empty():
                break
            try:
                task_result = self._client.get_task_result(task_id)
            except Exception:
                pass
            await asyncio.sleep(1)
        return task_result

    async def _generate_response(self, chat_history: List[gr.ChatMessage]):
        user_message = gr.ChatMessage(**chat_history[-1])
        task_id = self._client.create_task(user_message.content)
        message = gr.ChatMessage(
            role="assistant", content=f"Successfully submitted task: {task_id}."
        )
        chat_history.append(message)
        return chat_history, ""

    def _reset_chat(self) -> Tuple[str, str, str]:
        return "", "", None  # clear textboxes


app = HumanInTheLoopGradioApp(asyncio.Queue(), asyncio.Queue()).app

if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", server_port=8080)
