"""Web scraper and vector search workflows."""

from .workflows import scraper_workflow, search_workflow

__all__ = ["scraper_workflow", "search_workflow"]


def main() -> None:
    print("Hello from mcp!")
