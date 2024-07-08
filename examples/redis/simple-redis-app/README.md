# Example: Launching a Multi-Agent System with Redis

This example demonstrates how to build and launch a multi-agent system using Redis as the message queue. The example includes a simple script to launch the system and a `docker-compose` file to set up a Redis server.

## Prerequisites

- Docker and Docker Compose installed. (See [here](https://docs.docker.com/get-docker/) for installation instructions.)

## Installation

To run these examples, you'll need to have `llama-agents` installed with the `redis` extra:

```sh
# Using pip
pip install llama-agents[redis]

# Using Poetry
poetry add llama-agents -E "redis"
```

To run the example scripts, you also need to install the libraries used in the example scripts:

```sh
poetry install
```

## Usage Pattern

```python
from llama_agents.message_queue.redis import RedisMessageQueue

message_queue = RedisMessageQueue(
    url=...  # if no URL is supplied, the default redis://localhost:6379 is used
)
```

## Example

### Setting Up Redis

First, we need to set up a Redis server:

```sh
docker-compose up -d
```

This command will start a Redis server on port 6379.

### Running the Example Scripts

With the Redis server running, we can now run our example script to launch the multi-agent system.

```sh
# Using LocalLauncher
poetry run python ./simple-scripts/local_launcher_example.py
```

The script above will build a simple multi-agent app, connect it to the Redis message queue, and subsequently send the specified task.
