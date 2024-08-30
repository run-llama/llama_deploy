"""Utility functions for tools."""


def get_tool_name_from_service_name(service_name: str) -> str:
    """Utility function for getting the reserved name of a tool derived by a service."""
    return f"{service_name}-as-tool"
