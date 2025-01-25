import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "llama_deploy.apiserver:app",
        host=os.environ.get("LLAMA_DEPLOY_APISERVER_HOST", "0.0.0.0"),
        port=int(os.environ.get("LLAMA_DEPLOY_APISERVER_PORT", 4501)),
    )
