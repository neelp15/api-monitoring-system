
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CheckResultResponse(BaseModel):
    id: int
    monitor_id: int
    status_code: int | None
    response_time_ms: int | None
    status: str
    error_message: str | None
    checked_at: datetime

    model_config = ConfigDict(from_attributes=True)
