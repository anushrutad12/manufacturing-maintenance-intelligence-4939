from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AlertOut(BaseModel):
    """Alert returned to frontend."""

    id: str = Field(..., description="External alert id for UI.")
    equipmentId: str
    title: str
    parameter: str
    value: float
    unit: Optional[str] = None
    severity: str = Field(..., description="LOW|MEDIUM|HIGH|CRITICAL")
    score: int = Field(..., description="Priority score 0-100")
    status: str = Field(..., description="Open/Triaged/Closed style for UI mapping.")
    createdAt: datetime
    description: str = ""

    class Config:
        from_attributes = True


class AlertStatusPatch(BaseModel):
    """Patch alert status."""

    status: str = Field(..., description="New status: OPEN|ACKNOWLEDGED|IN_PROGRESS|RESOLVED|DISMISSED")
    actor: Optional[str] = Field(default=None, description="User performing the action.")
    note: Optional[str] = Field(default=None, description="Optional note for audit/resolution.")
