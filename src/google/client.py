import asyncio

from googleapiclient.discovery import build

from src.auth.token_manager import get_valid_credentials


async def get_calendar_service(user_id: str):
    """
    Build an authenticated Google Calendar API service for a specific user.
    Raises RuntimeError if the user hasn't authorized yet.
    """
    creds = await get_valid_credentials(user_id)
    if creds is None:
        raise RuntimeError(
            f"User '{user_id}' has not connected Google Calendar. "
            f"Call GET /api/calendar/auth/start?user_id={user_id} first."
        )
    return await asyncio.to_thread(
        build, "calendar", "v3", credentials=creds, cache_discovery=False
    )
