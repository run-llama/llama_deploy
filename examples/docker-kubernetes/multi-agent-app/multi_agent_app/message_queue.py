import os
from llama_agents import SimpleMessageQueue

try:
    message_queue_host = os.environ["MESSAGE_QUEUE_HOST"]
except KeyError:
    raise ValueError("Missing env var `MESSAGE_QUEUE_HOST`.")

message_queue = SimpleMessageQueue(host=message_queue_host, port=8000)
app = message_queue._app
