import uvicorn


if __name__ == "__main__":
    uvicorn.run("apiserver:app", host="localhost", port=4501)
