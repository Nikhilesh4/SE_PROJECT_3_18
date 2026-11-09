"""A tiny stdio MCP server used to test the external-server host."""
from mcp.server.mcpserver import MCPServer

mcp = MCPServer("fake-external")


@mcp.tool()
def list_events(day: str) -> str:
    """List calendar events."""
    return f"events on {day}: standup"


@mcp.tool()
def create_event(title: str) -> str:
    """Create a calendar event."""
    return f"created {title}"


@mcp.tool()
def send_email(to: str) -> str:
    """Send an email."""
    return "sent"


@mcp.tool()
def delete_event(id: str) -> str:
    """Delete an event."""
    return "deleted"


if __name__ == "__main__":
    mcp.run("stdio")
