import uvicorn


if __name__ == "__main__":
    uvicorn.run("llama_deploy.apiserver:app", host="0.0.0.0", port=4501)
