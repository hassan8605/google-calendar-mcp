import asyncio
import json
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from src.settings import settings

_write_lock = asyncio.Lock()

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _user_token_path(user_id: str) -> Path:
    """Returns path: {TOKENS_DIR}/{user_id}.json"""
    tokens_dir = Path(os.path.expanduser(settings.GOOGLE_TOKENS_DIR))
    return tokens_dir / f"{user_id}.json"


async def load_credentials(user_id: str) -> Credentials | None:
    """Load credentials for a specific user. Returns None if not found."""
    path = _user_token_path(user_id)
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return Credentials.from_authorized_user_info(data, SCOPES)


def _write_sync(path: Path, creds: Credentials) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(creds.to_json())


async def save_credentials(user_id: str, creds: Credentials) -> None:
    """Persist credentials for a specific user."""
    path = _user_token_path(user_id)
    async with _write_lock:
        await asyncio.to_thread(_write_sync, path, creds)


async def get_valid_credentials(user_id: str) -> Credentials | None:
    """Load and refresh credentials if expired. Returns None if user hasn't authorized."""
    creds = await load_credentials(user_id)
    if creds is None:
        return None
    if creds.expired and creds.refresh_token:
        await asyncio.to_thread(creds.refresh, Request())
        await save_credentials(user_id, creds)
    return creds


async def delete_credentials(user_id: str) -> None:
    """Remove a user's token file (logout)."""
    path = _user_token_path(user_id)
    async with _write_lock:
        if path.exists():
            path.unlink()


async def list_authorized_users() -> list[str]:
    """Return all user_ids that have authorized (have a token file)."""
    tokens_dir = Path(os.path.expanduser(settings.GOOGLE_TOKENS_DIR))
    if not tokens_dir.exists():
        return []
    return [f.stem for f in tokens_dir.glob("*.json")]
