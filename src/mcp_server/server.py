"""
MCP server exposing all 10 Google Calendar tools via FastMCP (SSE transport).

When mounted in the FastAPI app at /mcp:
  - SSE endpoint:      GET  /mcp/sse
  - Message endpoint:  POST /mcp/messages

Claude Desktop config (%APPDATA%\\Claude\\claude_desktop_config.json):
    {
      "mcpServers": {
        "calendar": {
          "url": "http://localhost:4325/mcp/sse",
          "transport": "sse"
        }
      }
    }
"""

import json
import structlog
from mcp.server.fastmcp import FastMCP

from src.google import tools as cal_tools

logger = structlog.get_logger(__name__)


def create_mcp_server() -> FastMCP:
    mcp = FastMCP(name="calendar-mcp")

    @mcp.tool()
    async def list_calendars() -> str:
        """List all Google Calendars the user has access to."""
        try:
            return json.dumps(await cal_tools.list_calendars(), default=str)
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    @mcp.tool()
    async def list_events(
        calendar_id: str = "primary",
        time_min: str = "",
        time_max: str = "",
        max_results: int = 10,
    ) -> str:
        """
        List events from a calendar.
        Use time_min / time_max (RFC3339, e.g. '2025-04-13T00:00:00Z') to filter by date.
        """
        try:
            return json.dumps(
                await cal_tools.list_events(
                    calendar_id=calendar_id,
                    time_min=time_min or None,
                    time_max=time_max or None,
                    max_results=max_results,
                ),
                default=str,
            )
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    @mcp.tool()
    async def search_events(
        query: str,
        calendar_id: str = "primary",
        max_results: int = 10,
    ) -> str:
        """Full-text search for calendar events matching a query string."""
        try:
            return json.dumps(
                await cal_tools.search_events(query=query, calendar_id=calendar_id, max_results=max_results),
                default=str,
            )
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    @mcp.tool()
    async def get_event(event_id: str, calendar_id: str = "primary") -> str:
        """Fetch a single calendar event by its event ID."""
        try:
            return json.dumps(await cal_tools.get_event(event_id=event_id, calendar_id=calendar_id), default=str)
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    @mcp.tool()
    async def create_event(
        summary: str,
        start_datetime: str,
        end_datetime: str,
        calendar_id: str = "primary",
        description: str = "",
        location: str = "",
        timezone: str = "UTC",
    ) -> str:
        """
        Create a new Google Calendar event.
        start_datetime and end_datetime must be ISO-8601 with timezone offset,
        e.g. '2025-04-14T14:00:00+05:00'.
        """
        try:
            return json.dumps(
                await cal_tools.create_event(
                    summary=summary,
                    start_datetime=start_datetime,
                    end_datetime=end_datetime,
                    calendar_id=calendar_id,
                    description=description or None,
                    location=location or None,
                    timezone=timezone,
                ),
                default=str,
            )
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    @mcp.tool()
    async def update_event(
        event_id: str,
        calendar_id: str = "primary",
        summary: str = "",
        start_datetime: str = "",
        end_datetime: str = "",
        description: str = "",
        location: str = "",
        timezone: str = "UTC",
    ) -> str:
        """Update fields on an existing event. Only non-empty fields are changed."""
        try:
            return json.dumps(
                await cal_tools.update_event(
                    event_id=event_id,
                    calendar_id=calendar_id,
                    summary=summary or None,
                    start_datetime=start_datetime or None,
                    end_datetime=end_datetime or None,
                    description=description or None,
                    location=location or None,
                    timezone=timezone,
                ),
                default=str,
            )
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    @mcp.tool()
    async def delete_event(event_id: str, calendar_id: str = "primary") -> str:
        """Permanently delete a calendar event by its event ID."""
        try:
            return json.dumps(await cal_tools.delete_event(event_id=event_id, calendar_id=calendar_id))
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    @mcp.tool()
    async def get_freebusy(
        time_min: str,
        time_max: str,
        calendar_ids: str = "",
    ) -> str:
        """
        Query free/busy slots for calendars within a time window.
        time_min and time_max must be RFC3339. calendar_ids is comma-separated (optional).
        """
        try:
            ids = [c.strip() for c in calendar_ids.split(",") if c.strip()] or None
            return json.dumps(
                await cal_tools.get_freebusy(time_min=time_min, time_max=time_max, calendar_ids=ids),
                default=str,
            )
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    @mcp.tool()
    async def get_current_time(timezone: str = "UTC") -> str:
        """
        Get the current date and time in the specified IANA timezone.
        Call this before interpreting relative times like 'tomorrow' or 'next week'.
        """
        try:
            return json.dumps(await cal_tools.get_current_time(timezone=timezone))
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    @mcp.tool()
    async def list_colors() -> str:
        """List the available color IDs for events and calendars."""
        try:
            return json.dumps(await cal_tools.list_colors())
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    return mcp
