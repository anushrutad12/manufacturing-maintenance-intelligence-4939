from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Message(BaseModel):
    """Generic message response."""

    message: str = Field(..., description="Human readable message.")


class Pagination(BaseModel):
    """Simple pagination metadata."""

    total: int = Field(..., description="Total number of items available.")
    limit: int = Field(..., description="Limit used for this response.")
    offset: int = Field(..., description="Offset used for this response.")


class AuditEventOut(BaseModel):
    """Audit event projection."""

    id: int
    entity_type: str
    entity_id: Optional[int] = None
    action: str
    actor: Optional[str] = None
    details: Optional[dict] = None
    occurred_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True
