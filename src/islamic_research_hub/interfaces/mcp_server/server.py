"""MCP server exposing this library's research capabilities to MCP clients.

Every tool is a thin wrapper over an existing repository/service the
desktop app and CLIs already use (see `tools/*.py`, one module per
capability group) - no new persistence or document-formatting logic.
Deliberately excludes anything destructive or corpus-wide-admin
(deleting/merging books, re-running imports/migrations, the citation
detector rebuild) - those stay as CLIs a human runs directly.
"""

import argparse
import logging
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from islamic_research_hub.interfaces.mcp_server.tools.bookmark_tools import (
    register_bookmark_tools,
)
from islamic_research_hub.interfaces.mcp_server.tools.citation_tools import (
    register_citation_tools,
)
from islamic_research_hub.interfaces.mcp_server.tools.collection_tools import (
    register_collection_tools,
)
from islamic_research_hub.interfaces.mcp_server.tools.export_tools import register_export_tools
from islamic_research_hub.interfaces.mcp_server.tools.note_tools import register_note_tools
from islamic_research_hub.interfaces.mcp_server.tools.search_tools import register_search_tools
from islamic_research_hub.shared.logging_config import configure_logging

LOGGER = logging.getLogger(__name__)

# Unlike the CLIs (always run from the project root by convention), this
# server's working directory is chosen by whatever MCP client launches it
# (e.g. Claude Desktop defaults to C:\Windows\system32 on Windows) and can't
# be relied on - resolve paths relative to this file instead, the same fix
# already used for the packaged desktop exe (see interfaces/desktop_app/__main__.py).
_PROJECT_ROOT = Path(__file__).resolve().parents[4]

DEFAULT_DATABASE_PATH = _PROJECT_ROOT / "data" / "books.db"
DEFAULT_LOG_DIRECTORY = _PROJECT_ROOT / "logs"


def build_server(database_path: Path = DEFAULT_DATABASE_PATH) -> MCPServer:
    """Build the MCP server and register every tool group against `database_path`."""
    server = MCPServer("islamic-research-hub")
    register_search_tools(server, database_path)
    register_bookmark_tools(server, database_path)
    register_collection_tools(server, database_path)
    register_note_tools(server)
    register_citation_tools(server, database_path)
    register_export_tools(server, database_path)
    return server


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(description="Run the Islamic Research Hub MCP server.")
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DATABASE_PATH,
        help=f"Path to the master database (default: {DEFAULT_DATABASE_PATH})",
    )
    return parser


def main(arguments: list[str] | None = None) -> None:
    """Run the MCP server over stdio, for use from an MCP client's server config."""
    configure_logging(DEFAULT_LOG_DIRECTORY)
    args = build_parser().parse_args(arguments)
    LOGGER.info("Starting MCP server against database: %s", args.database)
    build_server(args.database).run()


if __name__ == "__main__":
    main()
