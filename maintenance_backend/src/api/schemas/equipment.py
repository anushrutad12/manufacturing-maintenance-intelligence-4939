from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class EquipmentThresholdBand(BaseModel):
    """Frontend-friendly threshold band for a parameter."""

    warn: float = Field(..., description="Warning threshold (high).")
    danger: float = Field(..., description="Danger/alarm threshold (high).")
    unit: Optional[str] = Field(default=None, description="Display unit for the parameter.")


class EquipmentCreate(BaseModel):
    """Create equipment payload matching the React service layer."""

    id: Optional[str] = Field(default=None, description="Optional external equipment id/asset tag.")
    name: str = Field(..., description="Equipment name.")
    area: str = Field(..., description="Area code or name.")
    model: Optional[str] = Field(default=None, description="Model string.")
    thresholds: Dict[str, Any] = Field(default_factory=dict, description="Map of parameter -> threshold band.")


class EquipmentOut(BaseModel):
    """Equipment list item expected by frontend."""

    id: str = Field(..., description="External id used by UI (asset tag).")
    name: str
    area: str
    model: Optional[str] = None
    thresholds: Dict[str, Any] = Field(default_factory=dict)
    status: str = Field(..., description='Derived health label e.g. "Healthy", "At Risk", "Critical".')
    updatedAt: datetime = Field(..., description="Last update timestamp.")

    class Config:
        from_attributes = True


class EquipmentDetailOut(EquipmentOut):
    """Detailed view with optional DB numeric id."""

    dbId: Optional[int] = Field(default=None, description="Internal numeric database id.")
