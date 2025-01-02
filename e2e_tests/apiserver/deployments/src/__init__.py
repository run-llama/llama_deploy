from .workflow import EchoWorkflow
from .workflow_reload import EchoWithPrompt

my_workflow = EchoWorkflow()
echo_workflow_en = EchoWithPrompt(prompt_msg="I have received:")
echo_workflow_it = EchoWithPrompt(prompt_msg="Ho ricevuto:")
