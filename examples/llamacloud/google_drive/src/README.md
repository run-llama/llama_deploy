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

The pipeline setup workflow (`setup_pipeline.py`) creates a data source from Google Drive and sets up a processing pipeline.

### Arguments

- `--data-source-name`: Name for your data source (required)
- `--folder-id`: Google Drive folder ID to index (required)
- `--pipeline-name`: Name for your pipeline (required)
- `--service-account-key`: Path to Google service account JSON key file (required)
- `--chunk-size`: Size of text chunks for processing (default: 1024)
- `--chunk-overlap`: Overlap between chunks (default: 20)

## Query Index

The query workflow (`query_index.py`) allows you to query your created index.

### Arguments

- `--index-name`: Name of the index to query (required)
- `--organization-id`: Your LlamaCloud organization ID (required)
- `--query`: The question you want to ask (required)
- `--project-name`: Project name (default: "Default")

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
python setup_pipeline.py \
  --data-source-name "<DATA SOURCE NAME>" \
  --folder-id "1abc...xyz" \
  --pipeline-name "<LLAMA CLOUD PIPELINE NAME>" \
  --service-account-key "./service-account.json"
```

2. Then query your index:
```bash
python query_index.py \
  --index-name "<LLAMA CLOUD PIPELINE NAME>" \
  --organization-id "<ORGANIZATION ID>" \
  --query "<QUERY>"
```
