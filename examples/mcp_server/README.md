# LlamaDeploy MCP Server Example

This example demonstrates how to deploy a LlamaDeploy workflow as an MCP (Model Context Protocol) remote server that
can be integrated with Claude Desktop or other MCP-compatible clients.

## Overview

The example includes a **StatusWorkflow** that checks the operational status of popular web services including GitHub,
Reddit, Cloudflare, Vercel, OpenAI, Linear, and Discord. The workflow fetches status information from each service's
status page API and returns the current operational status.

## Files

- `src/workflow.py` - Contains the StatusWorkflow implementation
- `deployment.yaml` - LlamaDeploy configuration file
- `README.md` - This documentation

## Quick Start

### 1. Launch the LlamaDeploy Server

```bash
llamactl serve deployment.yaml
```

This will start the server and make the workflow available as an MCP tool at `http://localhost:4501/mcp`.

### 2. Configure Claude Desktop

Add the following configuration to your Claude Desktop settings to connect to the MCP server:

```json
{
  "mcpServers": {
    "LlamaDeploy": {
      "command": "npx",
      "args": ["mcp-remote", "http://localhost:4501/mcp"]
    }
  }
}
```

### 3. Use in Claude Desktop

Once configured, you can ask Claude to check service statuses:
- "What's the status of GitHub?"
- "Check if OpenAI services are operational"
- "Is Discord working?"

## How It Works

1. The `StatusWorkflow` class defines a workflow with a single step that checks service status
2. The workflow accepts a service name and queries the corresponding status page API
3. LlamaDeploy serves this workflow as an MCP tool that can be called by Claude Desktop
4. The MCP integration allows Claude to invoke the workflow and return results in natural conversation

## Requirements

- LlamaDeploy installed and configured
- Node.js (for the `mcp-remote` package)
- Internet connection to access status page APIs
