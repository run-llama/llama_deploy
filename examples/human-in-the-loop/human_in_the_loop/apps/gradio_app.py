"""Gradio app."""

from enum import Enum
from dataclasses import dataclass, field
from io import StringIO
from typing import Any, List, Optional, Tuple
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
            tasks_state = gr.State([])
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
            with gr.Row():
                human_prompt = gr.Textbox(label="Human Prompt")

            timer = gr.Timer(2)

            # event listeners
            # message submit
            message.submit(
                self._handle_user_message,
                [message, current_task, tasks_state],
                [message, current_task, tasks_state, chat_window],
            )

            # tick
            timer.tick(self._tick_handler, tasks_state, [tasks_state])

            # clear chat
            clear.click(self._reset_chat, None, [message, chat_window, console])

            @gr.render(inputs=tasks_state)
            def render_datasets(tasks):
                human_needed = [
                    [t.input] for t in tasks if t.status == "human_required"
                ]
                completed = [[t.input] for t in tasks if t.status == "completed"]
                submitted = [[t.input] for t in tasks if t.status == "submitted"]
                with gr.Row():
                    with gr.Column():
                        markdown = gr.Markdown(visible=False)
                        submitted_tasks_dataset = gr.Dataset(
                            samples=submitted,
                            components=[markdown],
                            label="Submitted",
                        )
                    with gr.Column():
                        markdown = gr.Markdown(visible=False)
                        human_input_required_dataset = gr.Dataset(
                            components=[markdown],
                            samples=human_needed,
                            label="Human Input Required",
                            elem_classes="human-needed",
                        )
                    with gr.Column():
                        markdown = gr.Markdown(visible=False)
                        completed_tasks_dataset = gr.Dataset(
                            components=[markdown],
                            samples=completed,
                            label="Completed Tasks",
                            elem_classes="completed-tasks",
                        )

    async def _tick_handler(
        self,
        tasks: List[TaskModel],
    ) -> str:
        logger.info("tick_handler")
        try:
            dict = self.human_in_loop_queue.get_nowait()
            prompt = dict["prompt"]
            task_id = dict["task_id"]

            # find task with the provided task_id
            try:
                ix, task = next(
                    (ix, t) for ix, t in enumerate(tasks) if t.task_id == task_id
                )
                task.prompt = prompt
                task.status = TaskStatus.HUMAN_REQUIRED
                tasks[ix] = task
            except StopIteration:
                raise ValueError("Cannot find task in list of tasks.")
            logger.info("appended human input request.")
        except asyncio.QueueEmpty:
            logger.info("human input request queue is empty.")
            pass

        return tasks

    async def _handle_user_message(
        self, user_message: str, current_task: Optional[str], tasks: List[TaskModel]
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
            # task_id = self._client.create_task(user_message.content)
            task_id = "3"
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
            print(tasks)
            current_task = None

        return "", current_task, tasks + [task], task.chat_history

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
