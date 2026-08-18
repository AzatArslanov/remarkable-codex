from __future__ import annotations

from pathlib import Path

from .config import load_settings
from .mcp_tools import RemarkableTools, tool_contracts


_active_tools: RemarkableTools | None = None


def upload_markdown_handler(title: str, markdownText: str | None = None, filePath: str | None = None, dryRun: bool = True, confirmUpload: bool = False) -> dict:
    if _active_tools is None:
        raise RuntimeError("MCP server is not initialized")
    return _active_tools.upload_markdown(title=title, markdown_text=markdownText, file_path=filePath, dry_run=dryRun, confirm_upload=confirmUpload)


def build_server():
    try:
        from mcp.server.fastmcp import FastMCP
        from mcp.types import ToolAnnotations
    except ImportError as error:
        raise RuntimeError("install the 'mcp' optional dependency to run the MCP server") from error
    global _active_tools
    _active_tools = RemarkableTools.from_settings(load_settings(Path("/config/config.toml")))
    server = FastMCP("remarkable-publisher")
    server.tool(
        name="upload_markdown",
        description="Render Markdown text or a UTF-8 file as PDF and upload it to the reMarkable library. Dry-run is the default.",
        annotations=ToolAnnotations(**tool_contracts()["upload_markdown"]),
    )(upload_markdown_handler)
    return server


def main() -> None:
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()
