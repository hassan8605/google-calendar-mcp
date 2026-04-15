"""
Google Calendar tool implementations — all functions are user-scoped.

Every function takes `user_id` as its first argument so each call operates
on that specific user's authorized calendar. user_id is injected server-side
and never exposed to Claude in tool definitions.
"""

import asyncio
from datetime import datetime

import pytz

from src.google.client import get_calendar_service
from src.settings import settings


def _normalize_event(e: dict) -> dict:
    conference_data = e.get("conferenceData", {})
    meet_link = None
    for ep in conference_data.get("entryPoints", []):
        if ep.get("entryPointType") == "video":
            meet_link = ep.get("uri")
            break

    return {
        "id": e.get("id", ""),
        "summary": e.get("summary", ""),
        "description": e.get("description"),
        "location": e.get("location"),
        "start": e.get("start", {}),
        "end": e.get("end", {}),
        "status": e.get("status", ""),
        "html_link": e.get("htmlLink"),
        "meet_link": meet_link,
        "attendees": [
            {"email": a.get("email"), "response": a.get("responseStatus")}
            for a in e.get("attendees", [])
        ],
        "creator": e.get("creator", {}),
        "created": e.get("created"),
        "updated": e.get("updated"),
        "recurring_event_id": e.get("recurringEventId"),
    }


async def list_calendars(user_id: str) -> list[dict]:
    svc = await get_calendar_service(user_id)
    result = await asyncio.to_thread(svc.calendarList().list().execute)
    return [
        {
            "id": c["id"],
            "summary": c.get("summary", ""),
            "access_role": c.get("accessRole", ""),
            "primary": c.get("primary", False),
            "time_zone": c.get("timeZone", ""),
        }
        for c in result.get("items", [])
    ]


async def list_events(
    user_id: str,
    calendar_id: str = "primary",
    time_min: str | None = None,
    time_max: str | None = None,
    max_results: int = 10,
    single_events: bool = True,
    order_by: str = "startTime",
) -> list[dict]:
    svc = await get_calendar_service(user_id)
    kwargs: dict = {
        "calendarId": calendar_id,
        "maxResults": max_results,
        "singleEvents": single_events,
        "orderBy": order_by,
    }
    if time_min:
        kwargs["timeMin"] = time_min
    if time_max:
        kwargs["timeMax"] = time_max
    result = await asyncio.to_thread(svc.events().list(**kwargs).execute)
    return [_normalize_event(e) for e in result.get("items", [])]


async def search_events(
    user_id: str,
    query: str,
    calendar_id: str = "primary",
    max_results: int = 10,
) -> list[dict]:
    svc = await get_calendar_service(user_id)
    result = await asyncio.to_thread(
        svc.events()
        .list(
            calendarId=calendar_id,
            q=query,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute
    )
    return [_normalize_event(e) for e in result.get("items", [])]


async def get_event(user_id: str, event_id: str, calendar_id: str = "primary") -> dict:
    svc = await get_calendar_service(user_id)
    e = await asyncio.to_thread(
        svc.events().get(calendarId=calendar_id, eventId=event_id).execute
    )
    return _normalize_event(e)


async def create_event(
    user_id: str,
    summary: str,
    start_datetime: str,
    end_datetime: str,
    calendar_id: str = "primary",
    description: str | None = None,
    location: str | None = None,
    attendees: list[str] | None = None,
    timezone: str = "UTC",
    add_meet_link: bool = False,
) -> dict:
    import uuid

    svc = await get_calendar_service(user_id)
    body: dict = {
        "summary": summary,
        "start": {"dateTime": start_datetime, "timeZone": timezone},
        "end": {"dateTime": end_datetime, "timeZone": timezone},
    }
    if description:
        body["description"] = description
    if location:
        body["location"] = location
    if attendees:
        body["attendees"] = [{"email": addr} for addr in attendees]
    if add_meet_link:
        body["conferenceData"] = {
            "createRequest": {
                "requestId": str(uuid.uuid4()),
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        }

    conference_data_version = 1 if add_meet_link else 0
    event = await asyncio.to_thread(
        svc.events()
        .insert(calendarId=calendar_id, body=body, conferenceDataVersion=conference_data_version)
        .execute
    )
    return _normalize_event(event)


async def update_event(
    user_id: str,
    event_id: str,
    calendar_id: str = "primary",
    summary: str | None = None,
    start_datetime: str | None = None,
    end_datetime: str | None = None,
    description: str | None = None,
    location: str | None = None,
    timezone: str = "UTC",
) -> dict:
    svc = await get_calendar_service(user_id)
    existing = await asyncio.to_thread(
        svc.events().get(calendarId=calendar_id, eventId=event_id).execute
    )
    if summary is not None:
        existing["summary"] = summary
    if description is not None:
        existing["description"] = description
    if location is not None:
        existing["location"] = location
    if start_datetime is not None:
        existing["start"] = {"dateTime": start_datetime, "timeZone": timezone}
    if end_datetime is not None:
        existing["end"] = {"dateTime": end_datetime, "timeZone": timezone}
    updated = await asyncio.to_thread(
        svc.events().update(calendarId=calendar_id, eventId=event_id, body=existing).execute
    )
    return _normalize_event(updated)


async def delete_event(user_id: str, event_id: str, calendar_id: str = "primary") -> dict:
    svc = await get_calendar_service(user_id)
    await asyncio.to_thread(
        svc.events().delete(calendarId=calendar_id, eventId=event_id).execute
    )
    return {"deleted": True, "event_id": event_id}


async def get_freebusy(
    user_id: str,
    time_min: str,
    time_max: str,
    calendar_ids: list[str] | None = None,
) -> dict:
    svc = await get_calendar_service(user_id)
    ids = calendar_ids or [settings.GOOGLE_DEFAULT_CALENDAR]
    body = {
        "timeMin": time_min,
        "timeMax": time_max,
        "items": [{"id": cid} for cid in ids],
    }
    result = await asyncio.to_thread(svc.freebusy().query(body=body).execute)
    return result.get("calendars", {})


async def get_current_time(user_id: str, timezone: str = "UTC") -> dict:
    """No API call — returns server clock in the requested timezone."""
    try:
        tz = pytz.timezone(timezone)
    except pytz.UnknownTimeZoneError:
        tz = pytz.utc
        timezone = "UTC"
    now = datetime.now(tz)
    return {
        "datetime": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "timezone": timezone,
        "utc_offset": now.strftime("%z"),
        "day_of_week": now.strftime("%A"),
    }


async def list_colors(user_id: str) -> dict:
    svc = await get_calendar_service(user_id)
    result = await asyncio.to_thread(svc.colors().get().execute)
    return {
        "event": result.get("event", {}),
        "calendar": result.get("calendar", {}),
    }
