from llama_agents import SimpleMessageQueue
from multi_agent_app.utils import load_from_env

message_queue_host = load_from_env("MESSAGE_QUEUE_HOST")
message_queue_port = load_from_env("MESSAGE_QUEUE_PORT")

message_queue = SimpleMessageQueue(
    host=message_queue_host,
    port=int(message_queue_port) if message_queue_port else None,
)
app = message_queue._app
