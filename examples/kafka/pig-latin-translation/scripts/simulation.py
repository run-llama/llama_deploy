import asyncio
import numpy as np
import random

from llama_agents import LlamaAgentsClient
from llama_index.llms.openai import OpenAI
from llama_index.core.llms import LLM


def pig_latin(text: str) -> str:
    tokens = text.lower().split()
    tmp = []
    for token in tokens:
        token = token[1:] + token[0] + "ay"
        tmp.append(token)
    return " ".join(tmp)


async def send_new_task(client: LlamaAgentsClient, llm: LLM) -> None:
    seed = random.random()
    num_tasks = np.random.poisson(2)
    for _ in range(num_tasks):
        response = await llm.acomplete(
            f"({seed}) Provide a 3 to 5 word phrase. Don't include any punctuation."
        )
        task = pig_latin(response.text)
        print(f"text: {response.text}, task: {task}")
        client.create_task(task)


async def main() -> None:
    client = LlamaAgentsClient("http://0.0.0.0:8001")
    llm = OpenAI("gpt-4o", temperature=1)
    try:
        while True:
            interarrival_time = np.random.exponential(3)
            await asyncio.sleep(interarrival_time)
            await send_new_task(client, llm)
    except KeyboardInterrupt:
        print("Shutting down.")


if __name__ == "__main__":
    asyncio.run(main())
