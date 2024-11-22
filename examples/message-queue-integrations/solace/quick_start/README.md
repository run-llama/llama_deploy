# Description
This example demonstrates how to run a workflow and interact with it. Two workflows have already been developed in the [deploy_workflow script](./deploy_core.py). The workflow responds to each query with a constant message. You can customize the deploy_workflow to add more features and functionalities to the agent.

## Installation
### Solace PubSub+ Event Broker
Install the [Solace PubSub+ event broker](https://docs.solace.com/Get-Started/Getting-Started-Try-Broker.htm).

#### Install Solace PubSub+ Python Package
```bash
pip install solace-pubsubplus
```

#### Verification
Open the PubSub+ interface in your browser. If you’re running PubSub+ locally, go to http://localhost:8080. Use ‘admin’ for both the username and password. Once the dashboard loads, click on ‘Try Me’ from the left-side menu. Then, subscribe to the 'llama_deploy.hello_workflow', 'llama_deploy.ping_workflow' and 'llama_deploy.control_plane' topics to monitor events.

## Run
Deploy the core on a terminal.

``` bash
python -m examples.message-queue-integrations.solace.quick_start.deploy_core
```

Deploy the workflow on a terminal.

``` bash
python -m examples.message-queue-integrations.solace.quick_start.deploy_workflow
```

Interact with the workflow. The below contains some interaction scenarios:

- The below module generates a task, which sends queries to a workflow sequentially.

``` bash
python -m examples.message-queue-integrations.solace.quick_start.interaction_simple
```

- The below command verifies that multiple requests can be handled by a workflow concurrently.

``` bash
python -m examples.message-queue-integrations.solace.quick_start.interaction_concurrent
```

- The below command verifies that multiple workflows can run simultaneously.

``` bash
python -m examples.message-queue-integrations.solace.quick_start.interaction_multi_flows
```
