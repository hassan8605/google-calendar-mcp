import structlog
from fastapi import APIRouter, Query

from src.auth.oauth import handle_oauth_callback, start_oauth_flow
from src.auth.token_manager import delete_credentials, get_valid_credentials, list_authorized_users
from src.nlp.service import process_schedule_request
from src.response import BuildJSONResponses
from src.schemas import ScheduleRequest

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/calendar")


# ── NLP scheduling ────────────────────────────────────────────

@router.post("/schedule")
async def schedule(request: ScheduleRequest):
    """
    Natural language calendar scheduling for a specific user.

    Example:
        {
            "user_id": "hassan",
            "message": "Schedule a 1-hour meeting tomorrow at 3pm",
            "timezone": "Asia/Karachi"
        }
    """
    try:
        result = await process_schedule_request(request)
        if result.succeeded:
            return BuildJSONResponses.success_response(
                data={"tool_calls_made": result.tool_calls_made},
                message=result.message,
            )
        return BuildJSONResponses.raise_exception(result.message)
    except RuntimeError as exc:
        return BuildJSONResponses.raise_exception(str(exc), status_code=401)
    except Exception as exc:
        logger.error("schedule_error", error=str(exc))
        return BuildJSONResponses.server_error(str(exc))


# ── OAuth flow ────────────────────────────────────────────────

@router.get("/auth/start")
async def auth_start(user_id: str = Query(..., description="Unique user identifier")):
    """
    Begin Google OAuth flow for a specific user.

    Usage: GET /api/calendar/auth/start?user_id=hassan
    Open the returned auth_url in a browser to authorize.
    """
    try:
        auth_url, state = start_oauth_flow(user_id)
        return BuildJSONResponses.success_response(
            data={"auth_url": auth_url, "state": state, "user_id": user_id},
            message=f"Open auth_url in a browser to connect Google Calendar for user '{user_id}'.",
        )
    except Exception as exc:
        logger.error("auth_start_error", error=str(exc))
        return BuildJSONResponses.server_error(str(exc))


@router.get("/auth/callback")
async def auth_callback(code: str, state: str):
    """
    Google OAuth callback — called automatically by Google after the user approves.
    Saves the token under the user_id that started the flow.
    """
    try:
        user_id = await handle_oauth_callback(code=code, state=state)
        return BuildJSONResponses.success_response(
            data={"user_id": user_id},
            message=f"Google Calendar connected for user '{user_id}'. They can now use POST /api/calendar/schedule.",
        )
    except ValueError as exc:
        return BuildJSONResponses.invalid_input(str(exc))
    except Exception as exc:
        logger.error("auth_callback_error", error=str(exc))
        return BuildJSONResponses.server_error(str(exc))


@router.get("/auth/status")
async def auth_status(user_id: str = Query(..., description="Unique user identifier")):
    """Check whether a specific user has connected their Google Calendar."""
    try:
        creds = await get_valid_credentials(user_id)
        if creds is None:
            return BuildJSONResponses.success_response(
                data={"authenticated": False, "user_id": user_id},
                message=f"User '{user_id}' has not connected Google Calendar.",
            )
        return BuildJSONResponses.success_response(
            data={
                "authenticated": True,
                "user_id": user_id,
                "expiry": creds.expiry.isoformat() if creds.expiry else None,
                "scopes": list(creds.scopes) if creds.scopes else [],
            },
            message=f"User '{user_id}' is authenticated.",
        )
    except Exception as exc:
        logger.error("auth_status_error", error=str(exc))
        return BuildJSONResponses.server_error(str(exc))


@router.delete("/auth/logout")
async def auth_logout(user_id: str = Query(..., description="Unique user identifier")):
    """Disconnect Google Calendar for a specific user (removes their token)."""
    try:
        await delete_credentials(user_id)
        return BuildJSONResponses.success_response(
            data={"user_id": user_id},
            message=f"Google Calendar disconnected for user '{user_id}'.",
        )
    except Exception as exc:
        logger.error("auth_logout_error", error=str(exc))
        return BuildJSONResponses.server_error(str(exc))


@router.get("/users")
async def list_users():
    """List all user_ids that have connected their Google Calendar."""
    try:
        users = await list_authorized_users()
        return BuildJSONResponses.success_response(
            data={"users": users, "count": len(users)},
            message=f"{len(users)} user(s) have connected Google Calendar.",
        )
    except Exception as exc:
        logger.error("list_users_error", error=str(exc))
        return BuildJSONResponses.server_error(str(exc))
