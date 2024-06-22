import json
import pickle
from typing import Any, Dict, List, Tuple

from llama_index.core.query_pipeline import QueryPipeline
from llama_index.core.tools import BaseTool

from agentfile.messages.base import QueueMessage
from agentfile.orchestrators.base import BaseOrchestrator
from agentfile.orchestrators.service_component import ServiceComponent
from agentfile.types import ActionTypes, TaskDefinition, TaskResult


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
        if "run_state" not in state:
            run_state = self.pipeline.get_run_state(input=task_def.input)
        else:
            run_state = pickle.loads(state["run_state"])

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

                # input to an agent is a dict, so we need to extract the actual input
                if isinstance(module_input, dict):
                    module_input = next(iter(module_input.values()))

                if isinstance(module, ServiceComponent):
                    found_service_component = True
                    next_service_keys.append(module_key)
                    next_messages.append(
                        QueueMessage(
                            type=module.name,
                            action=ActionTypes.NEW_TASK,
                            data=TaskDefinition(
                                input=module_input,
                                task_id=task_def.task_id,
                            ).model_dump(),
                        )
                    )
                    continue

                # run the module if it is not a service component
                output_dict = await module.arun_component(**module_input)

                if "service_output" in output_dict:
                    found_service_component = True
                    next_service_keys.append(module_key)
                    service_dict = json.loads(output_dict["service_output"])
                    next_messages.append(
                        QueueMessage(
                            type=service_dict["name"],
                            action=ActionTypes.NEW_TASK,
                            data=TaskDefinition(
                                input=service_dict["input"],
                                task_id=task_def.task_id,
                            ).model_dump(),
                        )
                    )
                    continue

                # process the output
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
        if len(next_service_keys) == 0 and len(next_messages) == 0:
            # no service component found, return the final result
            last_modules_run = state.get("last_modules_run", [])

            result_dict = run_state.result_outputs[module_key or last_modules_run[-1]]
            if len(result_dict) == 1:
                result = str(next(iter(result_dict.values())))
            else:
                result = str(result_dict)

            next_messages.append(
                QueueMessage(
                    type="human",
                    action=ActionTypes.COMPLETED_TASK,
                    data=TaskResult(
                        task_id=task_def.task_id,
                        result=result,
                        history=[],
                    ).model_dump(),
                )
            )

        new_state = {
            "run_state": pickle.dumps(run_state),
            "next_service_keys": next_service_keys,
        }
        return next_messages, new_state

    async def add_result_to_state(
        self,
        result: TaskResult,
        state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Add the result of processing a message to the state. Returns the new state."""

        run_state = pickle.loads(state["run_state"])
        next_service_keys = state["next_service_keys"]

        # process the output of the service component(s)
        for module_key in next_service_keys:
            self.pipeline.process_component_output(
                {"output": result.result},
                module_key,
                run_state,
            )

        return {
            "run_state": pickle.dumps(run_state),
            "last_modules_run": next_service_keys,
        }
