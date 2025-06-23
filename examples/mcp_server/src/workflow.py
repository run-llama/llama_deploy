import asyncio

import requests
from workflows import Workflow, step
from workflows.events import StartEvent, StopEvent

SERVICES = {
    "github": "https://kctbh9vrtdwd.statuspage.io/api/v2/status.json",
    "reddit": "https://reddit.statuspage.io/api/v2/status.json",
    "cloudflare": "https://yh6f0r4529hb.statuspage.io/api/v2/status.json",
    "vercel": "https://www.vercel-status.com/api/v2/status.json",
    "openai": "https://status.openai.com/api/v2/status.json",
    "linear": "https://linearstatus.com/api/v2/status.json",
    "discord": "https://discordstatus.com/api/v2/status.json",
}


class InputService(StartEvent):
    service_name: str


class StatusWorkflow(Workflow):
    """Reports the operational status for notable public services.

    This workflow can report status for major services like OpenAI, Github and Discord
    """

    @step
    async def check_status(self, ev: InputService) -> StopEvent:
        try:
            res = requests.get(SERVICES[ev.service_name.lower()], timeout=5)
            res.raise_for_status()
            data = res.json()
            status = data["status"]["description"]
            return StopEvent(status)
        except Exception as e:
            return StopEvent(f"{ev.service_name}: ERROR - {e}")


statuspage_workflow = StatusWorkflow()


async def main():
    print("🔍 Checking service statuses...\n")
    for name in SERVICES:
        print(
            name,
            await statuspage_workflow.run(start_event=InputService(service_name=name)),
        )


if __name__ == "__main__":
    asyncio.run(main())
