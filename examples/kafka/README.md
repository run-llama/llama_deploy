# Using Apache Kafka as the MessageQueue

The examples contained in this subdirectory make use of the Apache Kafka integration
within `llama-agents`.

To run these examples, you'll need to have the installed the `kafka` extra:

```sh
# using pip install
pip install llama-agents[kafka]

# using poetry
poetry add llama-agents -E "kafka"
```

## Usage Pattern

```python
from llama_agents.message_queue.apache_kafka import KafkaMessageQueue

message_queue = KafkaMessageQueue(
    url=...
)  # if no url is supplied the default localhost:9092 is used
```

## Examples

### Simple Scripts

A couple of scripts using `LocalLauncher` and a `LocalServer` with
`KafkaMessageQueue` (rather than `SimpleMessageQueue`) are included in this
subdirectory.

Before running any of these scrtips we first need to have Kafka cluster running.
For a quick setup, we recommend using the official Kafka community [docker image](https://hub.docker.com/r/apache/kafka):

```sh
docker run -p 9092:9092 apache/kafka:3.7.1
```

With our Kafka broker running, we can now run our example scripts.

```sh
# using LocalLauncher
python ./simple-scripts/local_launcher_human_single.py
```

The script above will build a simple multi-agent app, connect it to the Kafka
message queue, and subsequently send the specified task.

### Example App: Pig-Latin Translator
