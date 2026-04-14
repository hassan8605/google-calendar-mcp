"""
NLP scheduling service — Claude tool-use agentic loop (multi-user).

user_id is injected server-side into every tool call.
Claude never sees user_id — it only sees calendar tool names and their args.
"""

import json
import structlog
import anthropic
from functools import partial

from src.google import tools as cal_tools
from src.schemas import ScheduleRequest, ScheduleResponse
from src.settings import settings

logger = structlog.get_logger(__name__)

# ── Tool definitions shown to Claude (no user_id — injected server-side) ─

TOOL_DEFINITIONS: list[dict] = [
    {
        "name": "list_calendars",
        "description": "List all Google Calendars the user has access to.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "list_events",
        "description": (
            "List events from a calendar. Use time_min / time_max (RFC3339) to filter by date. "
            "Example: '2025-04-13T00:00:00Z'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "calendar_id": {"type": "string", "default": "primary"},
                "time_min": {"type": "string"},
                "time_max": {"type": "string"},
                "max_results": {"type": "integer", "default": 10},
            },
            "required": [],
        },
    },
    {
        "name": "search_events",
        "description": "Full-text search for calendar events.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "calendar_id": {"type": "string", "default": "primary"},
                "max_results": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_event",
        "description": "Fetch a single calendar event by its ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string"},
                "calendar_id": {"type": "string", "default": "primary"},
            },
            "required": ["event_id"],
        },
    },
    {
        "name": "create_event",
        "description": (
            "Create a new Google Calendar event. "
            "start_datetime and end_datetime must be ISO-8601 with timezone, "
            "e.g. '2025-04-14T14:00:00+05:00'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "start_datetime": {"type": "string"},
                "end_datetime": {"type": "string"},
                "calendar_id": {"type": "string", "default": "primary"},
                "description": {"type": "string"},
                "location": {"type": "string"},
                "attendees": {"type": "array", "items": {"type": "string"}},
                "timezone": {"type": "string", "default": "UTC"},
            },
            "required": ["summary", "start_datetime", "end_datetime"],
        },
    },
    {
        "name": "update_event",
        "description": "Update fields on an existing event. Only provided fields are changed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string"},
                "calendar_id": {"type": "string", "default": "primary"},
                "summary": {"type": "string"},
                "start_datetime": {"type": "string"},
                "end_datetime": {"type": "string"},
                "description": {"type": "string"},
                "location": {"type": "string"},
                "timezone": {"type": "string"},
            },
            "required": ["event_id"],
        },
    },
    {
        "name": "delete_event",
        "description": "Permanently delete a calendar event.",
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string"},
                "calendar_id": {"type": "string", "default": "primary"},
            },
            "required": ["event_id"],
        },
    },
    {
        "name": "get_freebusy",
        "description": "Check free/busy slots for calendars within a time window (RFC3339, max 3 months).",
        "input_schema": {
            "type": "object",
            "properties": {
                "time_min": {"type": "string"},
                "time_max": {"type": "string"},
                "calendar_ids": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["time_min", "time_max"],
        },
    },
    {
        "name": "get_current_time",
        "description": (
            "Get the current date and time in a given IANA timezone. "
            "ALWAYS call this first when the user uses relative terms like "
            "'tomorrow', 'next week', 'this Friday', etc."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "timezone": {"type": "string", "default": "UTC"},
            },
            "required": [],
        },
    },
    {
        "name": "list_colors",
        "description": "List available color IDs for events and calendars.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]

SYSTEM_PROMPT = """You are a Google Calendar assistant.
You have access to the user's Google Calendar via tools.

Rules:
- When the user mentions relative times ('tomorrow', 'next week', 'this Friday'),
  ALWAYS call get_current_time first to anchor the current date.
- Use ISO-8601 datetime strings with explicit timezone offsets for all event times.
- After creating, updating, or deleting an event, confirm what you did in plain language.
- If you need an event ID to update/delete, search for the event first.
- Be concise and helpful."""


def _build_dispatch(user_id: str) -> dict:
    """
    Build a tool dispatch map with user_id pre-bound via partial.
    Claude's tool args are passed as kwargs — user_id is injected here, not by Claude.
    """
    return {
        "list_calendars":  partial(cal_tools.list_calendars, user_id),
        "list_events":     partial(cal_tools.list_events, user_id),
        "search_events":   partial(cal_tools.search_events, user_id),
        "get_event":       partial(cal_tools.get_event, user_id),
        "create_event":    partial(cal_tools.create_event, user_id),
        "update_event":    partial(cal_tools.update_event, user_id),
        "delete_event":    partial(cal_tools.delete_event, user_id),
        "get_freebusy":    partial(cal_tools.get_freebusy, user_id),
        "get_current_time": partial(cal_tools.get_current_time, user_id),
        "list_colors":     partial(cal_tools.list_colors, user_id),
    }


async def process_schedule_request(request: ScheduleRequest) -> ScheduleResponse:
    log = logger.bind(user_id=request.user_id, message=request.message[:80])
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    dispatch = _build_dispatch(request.user_id)

    messages: list[dict] = [{"role": "user", "content": request.message}]
    tools_called: list[str] = []

    for iteration in range(10):
        log.info("claude_call", iteration=iteration)

        response = await client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOL_DEFINITIONS,  # type: ignore[arg-type]
            messages=messages,       # type: ignore[arg-type]
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            final_text = next(
                (b.text for b in response.content if b.type == "text"), "Done."
            )
            log.info("finished", tools=tools_called)
            return ScheduleResponse(
                succeeded=True,
                message=final_text,
                tool_calls_made=tools_called,
            )

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                tools_called.append(block.name)
                log.info("tool_call", tool=block.name)
                try:
                    fn = dispatch[block.name]
                    result = await fn(**block.input)  # type: ignore[operator]
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, default=str),
                    })
                except Exception as exc:
                    log.error("tool_error", tool=block.name, error=str(exc))
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": f"Error: {exc}",
                        "is_error": True,
                    })
            messages.append({"role": "user", "content": tool_results})
            continue

        break

    return ScheduleResponse(
        succeeded=False,
        message="Reached max tool iterations without a final answer.",
        tool_calls_made=tools_called,
    )
