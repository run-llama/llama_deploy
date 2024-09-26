import sys
from llama_deploy.cli import llamactl


def main() -> None:
    """CLI entrypoint."""
    sys.exit(llamactl())


if __name__ == "__main__":  # pragma: no cover
    main()
