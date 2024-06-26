from llama_agents import SimpleMessageQueue

message_queue = SimpleMessageQueue(host="0.0.0.0", port=8000)
app = message_queue._app
