# Examples using RabbitMQ Work Queues as the MessageQueue

The examples contained in this subdirectory make use of the RabbitMQ integration
within `llama-agents`.

To run these examples, you'll need to have the installed the `rabbitmq` extra:

```sh
# using pip install
pip install llama-agents[rabbitmq]

# using poetry
poetry add llama-agents -E "rabbitmq"
```

A running RabbitMQ server is also required. For a quick setup, we recommend using
the official RabbitMQ community docker image:

```sh
# latest RabbitMQ 3.13
docker run -it --rm --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3.13-management
```

## Usage Pattern

```python
from llama_agents.message_queue.rabbitmq import RabbitMQMessageQueue

message_queue = RabbitMQMessageQueue(
    url=...
)  # if no url is supplied the default localhost is used
```

## Examples

A couple of scripts using `LocalLauncher` and a `LocalServer` with
`RabbitMQMessageQueue` (rather than `SimpleMessageQueue`) are included in this
subdirectory. To run them use the commands below:

```sh
# using LocalLauncher
python local_launcher_example.py

# using ServerLauncher
python server_launcher_example.py
```
