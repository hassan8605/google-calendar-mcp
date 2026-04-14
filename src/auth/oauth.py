import asyncio

from google_auth_oauthlib.flow import Flow

from src.auth.token_manager import SCOPES, save_credentials
from src.settings import settings

# In-memory CSRF state store: {state_token: {"flow": Flow, "user_id": str}}
_pending_flows: dict[str, dict] = {}


def _build_client_config() -> dict:
    return {
        "web": {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }


def start_oauth_flow(user_id: str) -> tuple[str, str]:
    """
    Generate an authorization URL for a specific user.
    Returns (auth_url, state).
    The state carries the user_id so the callback knows whose token to save.
    """
    flow = Flow.from_client_config(
        _build_client_config(),
        scopes=SCOPES,
        redirect_uri=settings.GOOGLE_REDIRECT_URI,
    )
    auth_url, state = flow.authorization_url(
        access_type="offline",
    )
    _pending_flows[state] = {"flow": flow, "user_id": user_id}
    return auth_url, state


async def handle_oauth_callback(code: str, state: str) -> str:
    """
    Exchange authorization code for tokens and save under the correct user_id.
    Returns the user_id whose token was saved.
    Raises ValueError on invalid/expired state.
    """
    entry = _pending_flows.pop(state, None)
    if entry is None:
        raise ValueError("Unknown or expired OAuth state. Please restart the auth flow.")

    flow: Flow = entry["flow"]
    user_id: str = entry["user_id"]

    await asyncio.to_thread(flow.fetch_token, code=code)
    await save_credentials(user_id, flow.credentials)
    return user_id
