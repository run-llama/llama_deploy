from prometheus_client import Enum

apiserver_state = Enum(
    "apiserver_state",
    "Current state of the API server",
    states=[
        "starting",
        "running",
        "stopped",
    ],
)

deployment_state = Enum(
    "deployment_state",
    "Current state of a deployment",
    ["deployment_name"],
    states=[
        "loading_services",
        "ready",
        "starting_services",
        "running",
        "stopped",
    ],
)

service_state = Enum(
    "service_state",
    "Current state of a service attached to a deployment",
    ["deployment_name", "service_name"],
    states=[
        "loading",
        "syncing",
        "installing",
        "ready",
    ],
)
