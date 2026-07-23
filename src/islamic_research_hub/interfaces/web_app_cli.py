"""Launcher for the local web app: starts the server and opens a browser tab."""

import argparse
import threading
import webbrowser
from collections.abc import Sequence
from pathlib import Path

from islamic_research_hub.interfaces.web_app import DEFAULT_DATABASE_PATH, create_app

DEFAULT_PORT = 5000


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(description="Run the local search web app.")
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DATABASE_PATH,
        help=f"Path to the master database (default: {DEFAULT_DATABASE_PATH})",
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--no-browser", action="store_true", help="Do not open a browser tab automatically"
    )
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    """Start the web app and open it in the default browser."""
    args = build_parser().parse_args(arguments)
    app = create_app(args.database)
    url = f"http://127.0.0.1:{args.port}/"

    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    print(f"Islamic Research Hub is running at {url}")
    print("Press Ctrl+C to stop.")
    app.run(port=args.port, debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
