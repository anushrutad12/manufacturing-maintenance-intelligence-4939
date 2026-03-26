from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class LogCreate(BaseModel):
    """Create reading/log payload matching frontend."""

    equipmentId: str = Field(..., description="Equipment external id (asset tag).")
    parameter: str = Field(..., description="Parameter name (e.g., Temperature).")
    value: float = Field(..., description="Measured value.")
    unit: Optional[str] = Field(default=None, description="Unit string (optional).")
    recordedBy: str = Field(..., description='Who recorded the value: "sensor" or "operator".')
    note: Optional[str] = Field(default=None, description="Optional note.")


class LogOut(BaseModel):
    """Reading/log returned to frontend."""

    id: str = Field(..., description="External log id for UI.")
    equipmentId: str
    parameter: str
    value: float
    unit: Optional[str] = None
    recordedAt: datetime
    recordedBy: str
    note: str = ""

    class Config:
        from_attributes = True
