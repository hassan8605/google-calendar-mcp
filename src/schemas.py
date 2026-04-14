from typing import Any, Optional
from pydantic import BaseModel, Field


class ScheduleRequest(BaseModel):
    user_id: str = Field(..., description="Unique identifier for the user (e.g. email or UUID)")
    message: str = Field(..., description="Plain English calendar instruction")
    timezone: str = Field("UTC", description="IANA timezone, e.g. 'Asia/Karachi'")


class ScheduleResponse(BaseModel):
    succeeded: bool
    message: str
    data: Optional[dict[str, Any]] = None
    tool_calls_made: list[str] = []
