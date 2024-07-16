"""Gradio app."""

from enum import Enum
from dataclasses import dataclass, field
from io import StringIO
from typing import Any, Dict, List, Optional, Tuple
import asyncio
import gradio as gr
import sys

from llama_agents import LlamaAgentsClient
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


SAMPLE_TASKS = [
    TaskModel(
        task_id="1",
        input="What is 1+1?",
        status=TaskStatus.SUBMITTED,
        chat_history=[gr.ChatMessage(role="user", content="What is 1+1?")],
    ),
    TaskModel(
        task_id="2",
        input="What is 1-1?",
        status=TaskStatus.COMPLETED,
        chat_history=[
            gr.ChatMessage(role="user", content="What is 1-1?"),
            gr.ChatMessage(role="assistant", content="0."),
        ],
    ),
    TaskModel(
        task_id="3",
        input="What is 0*0?",
        status=TaskStatus.HUMAN_REQUIRED,
        chat_history=[
            gr.ChatMessage(role="user", content="What is 0*0?"),
            gr.ChatMessage(
                role="assistant",
                content="Your input is needed.",
                metadata={"title": "Agent needs your input."},
            ),
        ],
    ),
]


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
        logger.info(f"{human_in_loop_queue.empty()}")
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
        self._tasks: List[TaskModel] = SAMPLE_TASKS

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

            # event listeners
            # message submit
            message.submit(
                self._handle_user_message,
                [message, current_task, submitted_tasks_state],
                [message, current_task, submitted_tasks_state, chat_window],
            )

            # tick
            timer.tick(
                self._tick_handler,
                [
                    submitted_tasks_state,
                    human_required_tasks_state,
                    completed_tasks_state,
                ],
                [
                    submitted_tasks_state,
                    human_required_tasks_state,
                    completed_tasks_state,
                ],
            )

            # clear chat
            clear.click(self._reset_chat, None, [message, chat_window, console])

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
                            return task.chat_history

                        markdown = gr.Markdown(visible=False)
                        submitted_tasks_dataset = gr.Dataset(
                            samples=submitted_sample,
                            components=[markdown],
                            label="Submitted",
                        )
                        submitted_tasks_dataset.select(
                            _handle_selection_submitted,
                            [submitted_tasks_dataset],
                            chat_window,
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
                            return task.chat_history

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
                            chat_window,
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
                            return task.chat_history

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
                            chat_window,
                        )

    async def _tick_handler(
        self,
        submitted: List[TaskModel],
        human_needed: List[TaskModel],
        completed: List[TaskModel],
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
                del submitted[ix]
                human_needed.append(task)
            except StopIteration:
                raise ValueError("Cannot find task in list of tasks.")
            logger.info("appended human input request.")
        except asyncio.QueueEmpty:
            logger.info("human input request queue is empty.")
            pass

        return submitted, human_needed, completed

    async def _handle_user_message(
        self, user_message: str, current_task: Optional[str], submitted: List[TaskModel]
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
            ...
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
            current_task = None

        return "", current_task, submitted + [task], task.chat_history

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

        # # poll for tool_call_result with max timeout
        # try:
        #     task_result = await asyncio.wait_for(
        #         self._poll_for_task_result(task_id=task_id),
        #         timeout=self._timeout,
        #     )
        # except (
        #     asyncio.exceptions.TimeoutError,
        #     asyncio.TimeoutError,
        #     TimeoutError,
        # ) as e:
        #     logger.debug(f"Timeout reached for task with id {task_id}")
        #     if self._raise_timeout:
        #         raise
        #     task_result = TaskResult(
        #         task_id=task_id,
        #         result="Encountered error: " + str(e),
        #         history=[],
        #         data={"error": str(e)},
        #     )

        # # update assistant message
        # assistant_message = gr.ChatMessage(role="assistant", content=task_result.result)
        # chat_history.append(assistant_message)

        # return chat_history, ""

    def _reset_chat(self) -> Tuple[str, str, str]:
        return "", "", ""  # clear textboxes


app = HumanInTheLoopGradioApp(asyncio.Queue(), asyncio.Queue()).app

if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", server_port=8080)
