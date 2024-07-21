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

In this example, we build a multi-agent app for translating simple Pig-Latin,
where when given a sentence, all words in the sentence are modified with the
following two steps:

1. the first letter is moved to the end of the word
2. the suffix "ay" is added to the end of the word

For example: "hi how are you" becomes "eyhay owhay siay tiay oinggay" in simple
Pig-Latin.

The multi-agent system translate's simple Pig-Latin text by reversing the
previously mentioned two steps. It does so by using two agents that work in
sequence: `remove_ay_agent` and `correct_first_character_agent`.

#### Launching Without Docker

As with running our example simple scripts above, we need to standup our
Kafka node manually:

```sh
docker run -p 9092:9092 apache/kafka:3.7.1
```

Next, in order to launch this multi-agent system, we first need to set the
required environment variables. To do that fill in the provided
`template.env.local` file found in the `pig-latin-translation/` folder. After filling
in the file rename it to `.env.local` (i.e., remove "template" from the name)
and the run the commands that follow.

```sh
# set environment variables
cd pig-latin-translation
set -a && source .env.local

# activate the project virtual env
poetry shell && poetry install
```

Finally to launch the example multi-agent app:

```sh
python pig_lating_translation/local_launcher.py
```

Once launched, we can send tasks to our multi-agent system using the
`LlamaAgentsClient` (note: the code below introduce static delay to handle
asynchronous call for quick test purpose only):

```python
from llama_agents import LlamaAgentsClient
import time

client = LlamaAgentsClient("http://0.0.0.0:8001")
task_id = client.create_task("lamaindexlay siay hetay estbay")
time.sleep(10)
task_result = client.get_task_result(task_id)
print(task_result.result)
```

#### Launching With Docker

_Prerequisites_: Must have docker installed. (See
[here](https://docs.docker.com/get-docker/) for how to install Docker Desktop
which comes with `docker-compose`.)

**NOTE:** In this example, we don't need to run the Kafka server manually. So you
can go ahead and shutdown the Kafka docker container that we had running in
previous launch if you haven't yet done so. The Kafka server is bundled within
the multi-agent deployment defined in the `docker-compose.yaml` file.

To Launch with Docker, this example makes use of `docker-compose` that will take
care of launching the individual services (and building a default bridge network
so that the services/containers can communicate with one another by name.).

Before building the docker image and launching the services (as with the case
for launching without Docker), we first need to set the required environment
variables. Fill in the values in the `template.env.docker` file and after doing so rename
the file to `.env.docker`. Note there are some variables there that we recommend
not modifying as they are used to the service definitions establisehed in the
`docker_compose.yml`.

This example is provided without a `poetry.lock` file as recommended in the
[poetry documentation for library developers](https://python-poetry.org/docs/basic-usage/#as-a-library-developer).
Before running docker-compose the first time, we must create the `poetry.lock`
file. If you are coming from the previous section where we Launched Without
Docker, then you have obtained the lock file after running `poetry install`.
If not, then use the command below

```sh
# while in pig-latin-translation/
poetry install
```

To launch the services we now use the `docker-compose` command line tool.

```sh
docker-compose up --build
```

This command will start the servers in sequence: first the Kafka service,
then the control plane, followed by the agent services and the human consumer
service. This sequencing is required since the later services depend must register
to the message queue and control plane (and they need to be up and running before
being able to do so).

Once all the services are up and running, we can send tasks to our multi-agent
system:

```python
from llama_agents import LlamaAgentsClient
import time

client = LlamaAgentsClient("http://0.0.0.0:8001")
task_id = client.create_task("lamaindexlay siay hetay estbay")
time.sleep(10)
task_result = client.get_task_result(task_id)
print(task_result.result)
```
