import json
import pickle
from typing import Any, Dict, List, Tuple, Optional

from llama_index.core.query_pipeline import QueryPipeline
from llama_index.core.query_pipeline.query import RunState
from llama_index.core.tools import BaseTool

from llama_agents.messages.base import QueueMessage
from llama_agents.orchestrators.base import BaseOrchestrator
from llama_agents.tools.service_component import ServiceComponent, ModuleType
from llama_agents.types import ActionTypes, TaskDefinition, TaskResult

RUN_STATE_KEY = "run_state"
NEXT_SERVICE_KEYS = "next_service_keys"
LAST_MODULES_RUN = "last_modules_run"
RESULT_KEY = "result"


INPUT_DICT_KEY = "__input_dict__"





def get_service_component_message(
    module: ServiceComponent,
    task_id: str,
    input_dict: Dict[str, Any],
) -> QueueMessage:
    """Enqueue a service component message.

    This depends directly on whether the service component
    wraps an agent service or a component
    
    """
    if module.module_type == ModuleType.AGENT:
        # in an agent, assume input_dict is a single input
        input = next(iter(input_dict.values()))
        queue_message = QueueMessage(
            type=module.name,
            action=ActionTypes.NEW_TASK,
            data=TaskDefinition(
                input=input,
                task_id=task_id,
            ).model_dump()
        )
    elif module.module_type == ModuleType.COMPONENT:
        # in a component, input_dict is a dict
        queue_message = QueueMessage(
            type=module.name,
            action=ActionTypes.NEW_TASK,
            data=TaskDefinition(
                input="",
                task_id=task_id,
                state={"__input_dict__": input_dict} if input_dict else {},
            ).model_dump(),
        )
    else:
        raise ValueError("Invalid module type")

    return queue_message


def process_component_output(
    pipeline: QueryPipeline,
    run_state: RunState,
    module_key: str,
    task_result: TaskResult
) -> None:
    """Process component outputs.

    Take the task result and update the next modules in the pipeline.

    Propagate different data depending on the module type.
    
    """
    module = run_state.module_dict[module_key]
    if not isinstance(module, ServiceComponent):
        raise ValueError("Module is not a service component")

    if module.module_type == ModuleType.AGENT:
        # in an agent, the output is a single value
        pipeline.process_component_output(
            {"output": task_result.result},
            module_key,
            run_state,
        )
        return

    elif module.module_type == ModuleType.COMPONENT:
        # in a component, the output is a dict
        pipeline.process_component_output(
            task_result.data,
            module_key,
            run_state
        )
        
    else:
        raise ValueError("Invalid module type")


class PipelineOrchestrator(BaseOrchestrator):
    def __init__(
        self,
        pipeline: QueryPipeline,
    ):
        self.pipeline = pipeline

    async def get_next_messages(
        self, task_def: TaskDefinition, tools: List[BaseTool], state: Dict[str, Any]
    ) -> Tuple[List[QueueMessage], Dict[str, Any]]:
        # check if we need to init the state
        if RUN_STATE_KEY not in state:
            run_state = self.pipeline.get_run_state(input=task_def.input)
        else:
            run_state = pickle.loads(state[RUN_STATE_KEY])

        # run the next step in the pipeline, until we hit a service component
        next_module_keys = self.pipeline.get_next_module_keys(run_state)

        next_messages = []
        next_service_keys = []
        found_service_component = False
        module_key = None

        while len(next_module_keys) > 0:
            for module_key in next_module_keys:
                module = run_state.module_dict[module_key]
                module_input = run_state.all_module_inputs[module_key]

                if isinstance(module, ServiceComponent):

                    queue_message = get_service_component_message(
                        module,
                        task_def.task_id,
                        input_dict=module_input,
                    )

                    # # input to an agent is a dict, so we need to extract the actual input
                    # if isinstance(module_input, dict):
                    #     module_input = next(iter(module_input.values()))

                    found_service_component = True
                    next_service_keys.append(module_key)
                    next_messages.append(queue_message)
                    # next_messages.append(
                    #     QueueMessage(
                    #         type=module.name,
                    #         action=ActionTypes.NEW_TASK,
                    #         data=TaskDefinition(
                    #             input=module_input,
                    #             task_id=task_def.task_id,
                    #         ).model_dump(),
                    #     )
                    # )
                    continue

                # run the module if it is not a service component
                output_dict = await module.arun_component(**module_input)

                # check if the output is a service component
                if "service_output" in output_dict:
                    service_dict = json.loads(output_dict["service_output"])
                    found_service_component = True
                    next_service_keys.append(module_key)
                    queue_message = get_service_component_message(
                        module,
                        task_def.task_id,
                        input_dict=service_dict["input"],
                    )
                    # service_dict = json.loads(output_dict["service_output"])
                    # next_messages.append(
                    #     QueueMessage(
                    #         type=service_dict["name"],
                    #         action=ActionTypes.NEW_TASK,
                    #         data=TaskDefinition(
                    #             input=service_dict["input"],
                    #             task_id=task_def.task_id,
                    #         ).model_dump(),
                    #     )
                    # )
                    continue

                # process the output if it is not a service component
                self.pipeline.process_component_output(
                    output_dict,
                    module_key,
                    run_state,
                )

            if found_service_component:
                break

            # get the next module keys
            next_module_keys = self.pipeline.get_next_module_keys(
                run_state,
            )

            # if no more modules to run, break
            if len(next_module_keys) == 0:
                run_state.result_outputs[module_key] = output_dict
                break

        # did we find a service component?
        task_result = None
        if len(next_service_keys) == 0 and len(next_messages) == 0:
            # no service component found, return the final result
            last_modules_run = state.get(LAST_MODULES_RUN, [])

            result_dict = run_state.result_outputs[module_key or last_modules_run[-1]]
            if len(result_dict) == 1:
                result = str(next(iter(result_dict.values())))
            else:
                result = str(result_dict)

            task_result = TaskResult(
                task_id=task_def.task_id,
                result=result,
                history=[],
            )

            next_messages.append(
                QueueMessage(
                    type="human",
                    action=ActionTypes.COMPLETED_TASK,
                    data=task_result.model_dump(),
                )
            )

        state[RUN_STATE_KEY] = pickle.dumps(run_state)
        state[NEXT_SERVICE_KEYS] = next_service_keys
        state[RESULT_KEY] = (
            task_result.model_dump() if task_result is not None else None
        )

        return next_messages, state

    async def add_result_to_state(
        self,
        result: TaskResult,
        state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Add the result of processing a message to the state. Returns the new state."""

        run_state = pickle.loads(state[RUN_STATE_KEY])
        next_service_keys = state[NEXT_SERVICE_KEYS]

        # process the output of the service component(s)
        for module_key in next_service_keys:
            process_component_output(
                self.pipeline,
                run_state,
                module_key,
                result,
            )
            # self.pipeline.process_component_output(
            #     {"output": result.result},
            #     module_key,
            #     run_state,
            # )

        state[RUN_STATE_KEY] = pickle.dumps(run_state)
        state[LAST_MODULES_RUN] = next_service_keys
        return state
