Deployed workflows also publish the workflows as MCP tools. You can use this example as a scrapable knowledge store

Start the store:

From the root directory, run this to start the server:

```sh
LLAMA_DEPLOY_APISERVER_RC_PATH=$PWD/examples/mcp uv run uvicorn llama_deploy.apiserver.app:app
```

You can then configure your client to connect to the server. For example cursor:

```json
{
  "mcpServers": {
    "llama-deploy": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```
