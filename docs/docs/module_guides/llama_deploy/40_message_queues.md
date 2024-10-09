## Message Queue Integrations

In addition to `SimpleMessageQueue`, we provide integrations for various
message queue providers, such as RabbitMQ, Redis, etc. The general usage pattern
for any of these message queues is the same as that for `SimpleMessageQueue`,
however the appropriate extra would need to be installed along with `llama-deploy`.

For example, for `RabbitMQMessageQueue`, we need to install the "rabbitmq" extra:

```sh
# using pip install
pip install llama-agents[rabbitmq]

# using poetry
poetry add llama-agents -E "rabbitmq"
```

Using the `RabbitMQMessageQueue` is then done as follows:

```python
from llama_agents.message_queue.rabbitmq import (
    RabbitMQMessageQueueConfig,
    RabbitMQMessageQueue,
)

message_queue_config = (
    RabbitMQMessageQueueConfig()
)  # loads params from environment vars
message_queue = RabbitMQMessageQueue(**message_queue_config)
```

<!-- prettier-ignore-start -->
> [!NOTE]
> `RabbitMQMessageQueueConfig` can load its params from environment variables.
<!-- prettier-ignore-end -->
