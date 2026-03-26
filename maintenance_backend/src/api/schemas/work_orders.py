from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class WorkOrderFromAlertCreate(BaseModel):
    """Create a work order from an alert (frontend payload)."""

    alertId: str = Field(..., description="External alert id.")
    assignedTo: str = Field(..., description="Assignee username/name.")
    dueAt: str = Field(..., description="ISO timestamp string; backend will store due_date.")


class WorkOrderAction(BaseModel):
    """UI-friendly work order action log item."""

    at: datetime
    by: str
    note: str


class WorkOrderPartItem(BaseModel):
    """UI-friendly part item attached to a work order."""

    partId: str
    name: str
    qty: int


class WorkOrderClosure(BaseModel):
    """Work order closure payload returned to UI."""

    at: datetime
    closedBy: str
    notes: str


class WorkOrderOut(BaseModel):
    """Work order returned to frontend."""

    id: str
    equipmentId: str
    alertId: Optional[str] = None
    title: str
    priority: str
    assignedTo: Optional[str] = None
    status: str
    createdAt: datetime
    dueAt: Optional[str] = None
    actions: List[WorkOrderAction] = Field(default_factory=list)
    parts: List[WorkOrderPartItem] = Field(default_factory=list)
    closure: Optional[WorkOrderClosure] = None

    class Config:
        from_attributes = True


class WorkOrderPatch(BaseModel):
    """Patch fields of a work order."""

    status: Optional[str] = Field(default=None, description="New status.")
    assignedTo: Optional[str] = Field(default=None, description="New assignee.")
    title: Optional[str] = Field(default=None, description="Optional title update.")
    description: Optional[str] = Field(default=None, description="Optional description update.")


class WorkOrderClose(BaseModel):
    """Close work order payload."""

    id: str
    closedBy: str
    notes: str


class ReservePartsCreate(BaseModel):
    """Reserve parts request (frontend payload)."""

    workOrderId: str
    items: List[dict] = Field(..., description="Items: { partId: string, qty: number }")


class PartOut(BaseModel):
    """Part returned to frontend."""

    id: str
    name: str
    stock: int

    class Config:
        from_attributes = True
