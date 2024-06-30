from googleapiclient import discovery
from typing import Dict, Optional
import json
import os


class Perspective:
    """Custom class to interact with Perspective API."""

    attributes = [
        "toxicity",
        "severe_toxicity",
        "identity_attack",
        "insult",
        "profanity",
        "threat",
        "sexually_explicit",
    ]

    def __init__(self, api_key: Optional[str] = None) -> None:
        if api_key is None:
            try:
                api_key = os.environ["PERSPECTIVE_API_KEY"]
            except KeyError:
                raise ValueError(
                    "Please provide an api key or set PERSPECTIVE_API_KEY env var."
                )

        self._client = discovery.build(
            "commentanalyzer",
            "v1alpha1",
            developerKey=api_key,
            discoveryServiceUrl="https://commentanalyzer.googleapis.com/$discovery/rest?version=v1alpha1",
            static_discovery=False,
        )

    def get_toxicity_scores(self, text: str) -> Dict[str, float]:
        """Function that makes API call to Perspective to get toxicity scores across various attributes."""

        analyze_request = {
            "comment": {"text": text},
            "requestedAttributes": {att.upper(): {} for att in self.attributes},
        }

        response = self._client.comments().analyze(body=analyze_request).execute()
        try:
            return {
                att: response["attributeScores"][att.upper()]["summaryScore"]["value"]
                for att in self.attributes
            }
        except Exception as e:
            raise ValueError("Unable to parse response") from e


perspective = Perspective()


from typing import Tuple
from llama_index.core.bridge.pydantic import Field


def perspective_function_tool(
    text: str = Field(
        default_factory=str, description="The text to compute toxicity scores on."
    )
) -> Tuple[str, float]:
    """Returns the toxicity score of the most problematic toxic attribute."""

    scores = perspective.get_toxicity_scores(text=text)
    max_key = max(scores, key=scores.get)
    return (max_key, scores[max_key] * 100)


from llama_index.core.tools import FunctionTool

pespective_tool = FunctionTool.from_defaults(
    perspective_function_tool,
)

from llama_index.agent.introspective import IntrospectiveAgentWorker
from llama_index.agent.introspective import ToolInteractiveReflectionAgentWorker

from llama_index.llms.openai import OpenAI
from llama_index.agent.openai import OpenAIAgentWorker
from llama_index.core.agent import FunctionCallingAgentWorker
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core import ChatPromptTemplate


def get_tool_interactive_reflection_agent(verbose: bool = True):
    """Helper function for getting the tool-interactive reflection agent.

    Steps:

    Define the `ToolInteractiveReflectionAgentWorker`
    - Construct a CritiqueAgentWorker that performs reflection with tools.
    - Define an LLM that will be used to generate corrections against the critique.
    - Define a function that determines the stopping condition for reflection/correction
            cycles
    - Construct `ToolInteractiveReflectionAgentWorker` using .from_defaults()
    """
    critique_agent_worker = FunctionCallingAgentWorker.from_tools(
        tools=[pespective_tool], llm=OpenAI("gpt-3.5-turbo"), verbose=verbose
    )
    correction_llm = OpenAI("gpt-4-turbo-preview")
    def stopping_callable(critique_str: str) -> bool:
        """Function that determines stopping condition for reflection & correction cycles.

        critique_str [str]: The response string provided by the critique agent.
        """

        return "[PASS]" in critique_str

    
    
    agent_worker = ToolInteractiveReflectionAgentWorker.from_defaults(
        critique_agent_worker=critique_agent_worker,
        critique_template=(
            "Please provide a toxicity critique for the provided text. "
            "If the toxicity score is less than 3.0 then please "
            "write '[PASS]' otherwise write '[FAIL]'. "
            "Here is the text:\n {input_str}"
        ),
        stopping_callable=stopping_callable,
        correction_llm=correction_llm,
        verbose=verbose,
    )
    chat_history = [
        ChatMessage(
            content="You are an assistant that generates safer versions of potentially toxic, user-supplied text.",
            role=MessageRole.SYSTEM,
        )
    ]
    
    return agent_worker.as_agent(chat_history=chat_history)


critic_agent_prepackaged = get_tool_interactive_reflection_agent(verbose=True)



# wrap with stateful function
from llama_index.core.agent import FnAgentWorker
from typing import Dict, Any, Tuple

def critic_agent_fn(state: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    """Critic agent function."""
    critic_agent_prepackaged, input_str = state["critic_agent_prepackaged"], state["__task__"].input
    response = critic_agent_prepackaged.query(input_str)
    state["__output__"] = str(response)
    return state, True

critic_agent = FnAgentWorker(
    fn=critic_agent_fn, initial_state={
        "critic_agent_prepackaged": critic_agent_prepackaged, 
    }
).as_agent()

from llama_index.agent.introspective import SelfReflectionAgentWorker


def get_self_reflection_agent(verbose: bool = True):
    """Helper function for building a self reflection agent."""

    self_reflection_agent_worker = SelfReflectionAgentWorker.from_defaults(
        llm=OpenAI("gpt-4-turbo-preview"),
        verbose=verbose,
    )

    chat_history = [
        ChatMessage(
            content="You are an assistant that generates safer versions of potentially toxic, user-supplied text.",
            role=MessageRole.SYSTEM,
        )
    ]

    # 3b.
    return self_reflection_agent_worker.as_agent(
        chat_history=chat_history, verbose=verbose
    )


# self_reflection_agent_prepackaged = get_self_reflection_agent(verbose=True)
self_reflection_agent = get_self_reflection_agent(verbose=True)

# def self_reflection_agent_fn(state: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
#     """self reflection agent function."""
#     self_reflection_agent_prepackaged, input_str = state["self_reflection_agent_prepackaged"], state["__task__"].input
#     response = self_reflection_agent_prepackaged.query(input_str)
#     state["__output__"] = str(response)
#     return state, True

# self_reflection_agent = FnAgentWorker(
#     fn=self_reflection_agent_fn, initial_state={
#         "self_reflection_agent_prepackaged": self_reflection_agent_prepackaged, 
#     }
# ).as_agent()


### (jerry) gtgtTEST self-reflection agent to make sure it works

# harmful_text = (
#     "Those individuals who publicly tout eating no meat, "
#     "especially when their stated reason has to do with caring "
#     "about animals, are some of the most hypocritical people I’ve "
#     "ever met. One vegan acquaintance routinely beat her"
# )

# tmp_response = self_reflection_agent.query(harmful_text)
# print(str(tmp_response))


from llama_agents import (
    AgentService,
    AgentOrchestrator,
    ControlPlaneServer,
    ServerLauncher,
    LocalLauncher,
    SimpleMessageQueue,
    QueueMessage,
    CallableMessageConsumer
)
from llama_index.llms.openai import OpenAI


def get_launcher(agent, is_local: bool = True):
    # create our multi-agent framework components
    message_queue = SimpleMessageQueue()
    queue_client = message_queue.client

    control_plane = ControlPlaneServer(
        message_queue=queue_client,
        orchestrator=AgentOrchestrator(llm=OpenAI()),
    )

    agent_service = AgentService(
        agent=agent,
        message_queue=queue_client,
        description="A agent service that performs reflection.",
        service_name="reflection_service",
        host="127.0.0.1",
        port=8002,
    )
    # launch it
    if is_local:
        launcher = LocalLauncher(
            [agent_service], control_plane, message_queue
        )
    else:
        # Additional human consumer
        def handle_result(message: QueueMessage) -> None:
            print(f"Got result:", message.data)

        human_consumer = CallableMessageConsumer(
            handler=handle_result, message_type="human"
        )
        launcher = ServerLauncher(
            [agent_service], 
            control_plane, 
            message_queue,
            additional_consumers=[human_consumer]
        )

    return launcher


self_reflection_agent_launcher = get_launcher(self_reflection_agent, is_local=False)
self_reflection_agent_launcher.launch_servers()

# critic_agent_launcher = get_launcher(critic_agent, is_local=False)
# critic_agent_launcher.launch_servers()

# critic_agent_launcher = get_launcher(critic_agent)
# self_reflection_agent_launcher = get_launcher(self_reflection_agent)

# harmful_text = (
#     "Those individuals who publicly tout eating no meat, "
#     "especially when their stated reason has to do with caring "
#     "about animals, are some of the most hypocritical people I’ve "
#     "ever met. One vegan acquaintance routinely beat her"
# )
# response = critic_agent_launcher.launch_single(harmful_text)
# print(str(response))