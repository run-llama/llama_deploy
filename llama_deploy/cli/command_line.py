import argparse

from llama_deploy.app.app import run as launch_monitor


def main() -> None:
    parser = argparse.ArgumentParser(description="llama_deploy CLI interface.")

    # Subparsers for the main commands
    subparsers = parser.add_subparsers(title="commands", dest="command", required=True)

    # Subparser for the monitor command
    monitor_parser = subparsers.add_parser("monitor", help="Monitor the agents.")
    monitor_parser.add_argument(
        "--control-plane-url",
        default="http://127.0.0.1:8000",
        help="The URL of the control plane. Defaults to http://127.0.0.1:8000",
    )
    monitor_parser.set_defaults(
        func=lambda args: launch_monitor(args.control_plane_url)
    )

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
