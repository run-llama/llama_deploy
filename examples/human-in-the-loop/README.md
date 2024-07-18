# Human In The Loop w/ Gradio

In this example, we demonstrate how to utilize a `HumanService` as part of a
multi-agent system to enable a human-in-the-loop design frontend by a Gradio app.

<img src="https://d3ddy8balm3goa.cloudfront.net/llamaindex/human-in-the-loop.gif"/>


## The Multi-Agent System

The system consists of the following components:

- `AgentServer`: a single agent with `OpenAI` LLM that answers all queries except
  those having to do with math
- `HumanServer`: a service for humans to be able to answer queries on math
- `RabbitMQMessageQueue`: the message broker for communication of other components
- `ControlPlane` with `PipelineOrchestrator` that uses a single `RouterComponent`
  which selects between the `AgentServer` or the `HumanServer` when processing a
  task.

## Gradio App

We build the simple Gradio app where one can submit tasks to the system, watch
the task go through various stages in its lifecyle: namely, "Submittted",
"Completed", and "Human Required".

Technically speaking, the Gradio app is a `Consumer` of the message queue since
it listens for the messages that contain "completed" tasks notifications. This
front-end is also wired to the `HumanServer` so that the human in the loop can
use this interface to complete its tasks. Note, however that these two concerns
can be separated to other pages, webapps, servers to your choosing.

## Usage

The multi-agent system can be launched via Docker. An OPENAI_API_KEY environment
variable must be supplied, and can be done so by filling in the template .env file
named `template.env.docker`. After filling it out, rename the file to `.env.docker`.

With that out of the way, we can build/launch our multi-agent system app along with
our Gradio app.

```sh
# download data for the agentic rag
mkdir data
wget 'https://raw.githubusercontent.com/run-llama/llama_index/main/docs/docs/examples/data/paul_graham/paul_graham_essay.txt' -O 'data/paul_graham_essay.txt'

# launch the system
docker-compose up --build
```

Running this single command will launch everything that we need. It does so in
sequence: message queue, control plane, agent server & human server. Note that
the Gradio (fastapi) app is merely mounted to the human server app.

Once running, we can visit our browser and enter the host and port of the
Human Server app adding the necessary route to our Gradio app: [http://0.0.0.0:8003/gradio](http://0.0.0.0:8003/gradio]).
