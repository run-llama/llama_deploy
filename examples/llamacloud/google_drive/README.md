# Deploy LlamaCloud Pipeline with GoogleDrive Data Source

This repository contains two main workflows for working with LlamaCloud:
1. Setting up a LlamaCloud pipeline with Google Drive data source
2. Querying the created index

## Prerequisites

Before you begin, make sure you have:

1. Required Python packages:
```bash
pip install llama-index llama-index-indices-managed-llama-cloud llama-cloud
```

2. Required API keys set in your environment:
```bash
export OPENAI_API_KEY=your_openai_api_key
export LLAMA_CLOUD_API_KEY=your_llamacloud_api_key
```

3. A Google Drive service account key JSON file

## Setup Pipeline

The pipeline setup workflow (`src/setup_pipeline.py`) creates a data source from Google Drive and sets up a processing pipeline.

### Arguments

- `--data-source-name`: Name for your data source (required)
- `--folder-id`: Google Drive folder ID to index (required)
- `--pipeline-name`: Name for your pipeline (required)
- `--service-account-key`: Path to Google service account JSON key file (required)
- `--chunk-size`: Size of text chunks for processing (default: 1024)
- `--chunk-overlap`: Overlap between chunks (default: 20)

## Query Index

The query workflow (`src/workflow.py`) allows you to query your created index.

### Configuration File Version

Create a `config.yml` file in `src`:

```yaml
llamacloud:
  index_name: "<YOUR INDEX NAME>"
  project_name: "<YOUR PROJECT NAME>"
  organization_id: "<YOUR ORGANIZATION ID>"
```

## Workflow Structure

### Pipeline Setup Workflow

The pipeline setup process follows these steps:
1. Initialize LlamaCloud client
2. Create Google Drive data source
3. Set up processing pipeline with embeddings and transformations

### Query Workflow

The query process follows these steps:
1. Create LlamaCloud index connection
2. Set up query engine
3. Execute query and return results

## Environment Variables

Required environment variables:
- `OPENAI_API_KEY`: Your OpenAI API key for embeddings
- `LLAMA_CLOUD_API_KEY`: Your LlamaCloud API key

## Example Usage

1. First, set up your pipeline:
```bash
python src/setup_pipeline.py \
  --data-source-name "<DATA SOURCE NAME>" \
  --folder-id "<FOLDER ID>" \
  --pipeline-name "<LLAMA CLOUD PIPELINE NAME>" \
  --service-account-key "./service-account.json"
```

2. Then query your index:
```bash
python src/workflow.py
```

Note: You need to change the default query in `workflow.py`.

To be able to run the workflow above within LlamaDeploy, a deployment must be defined in YAML format. This is the code
you'll find in the file `deployment.yml` from the current folder, with comments to the relevant bits:

```yaml
name: LlamaCloud_LlamaDeploy_GoogleDrive

control-plane:
  port: 8000

default-service: llamacloud_workflow

services:
  llamacloud_workflow:
    name: LlamaCloud GoogleDrive Data Source Workflow
    # We tell LlamaDeploy where to look for our workflow
    source:
      # In this case, we instruct LlamaDeploy to look in the local filesystem
      type: local
      # The path relative to this deployment config file where to look for the code. This assumes
      # there's an src folder along with the config file containing the file workflow.py we created previously
      name: ./src
    # This assumes the file workflow.py contains a variable called `echo_workflow` containing our workflow instance
    path: workflow:llamacloud_workflow
```

The YAML code above defines the deployment that LlamaDeploy will create and run as a service. As you can
see, this deployment has a name, some configuration for the control plane and one service to wrap our workflow. The
service will look for a Python variable named `llamacloud_workflow` in a Python module named `workflow` and run the workflow.

At this point we have all we need to run this deployment. Ideally, we would have the API server already running
somewhere in the cloud, but to get started let's start an instance locally. Run the following python script
from a shell:

NOTE: You need to set up `OPENAI_API_KEY` and `LLAMA_CLOUD_API_KEY` again here.

```
$ python -m llama_deploy.apiserver
INFO:     Started server process [10842]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:4501 (Press CTRL+C to quit)
```

From another shell, use the CLI, `llamactl`, to create the deployment:

```
$ llamactl deploy deployment.yml
Deployment successful: LlamaCloud_LlamaDeploy_GoogleDrive
```

Our workflow is now part of the `LlamaCloud_LlamaDeploy_GoogleDrive` deployment and ready to serve requests! We can use `llamactl` to interact
with this deployment:

```
$ llamactl run --deployment LlamaCloud_LlamaDeploy_GoogleDrive --arg query '<YOUR QUERY>'
```

This will return a dictionary of query and response.
