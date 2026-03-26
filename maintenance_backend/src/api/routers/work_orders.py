from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from src.api.schemas.work_orders import (
    ReservePartsCreate,
    WorkOrderClose,
    WorkOrderFromAlertCreate,
    WorkOrderOut,
    WorkOrderPatch,
)
from src.db.models import Alert, Part, WorkOrder
from src.db.session import get_db
from src.domain.enums import AlertStatus, Severity, WorkOrderStatus
from src.services.repositories import reserve_parts_for_work_order

router = APIRouter(prefix="/work-orders", tags=["work_orders"])


def _parse_due_date(due_at: str) -> date | None:
    try:
        # Accept ISO date or datetime
        if "T" in due_at:
            return datetime.fromisoformat(due_at.replace("Z", "+00:00")).date()
        return date.fromisoformat(due_at)
    except Exception:
        return None


@router.get("", response_model=list[WorkOrderOut], summary="List work orders", description="List work orders, optionally filtered by status.")
def list_work_orders(status: str | None = Query(default=None), db: Session = Depends(get_db)):
    """List work orders."""
    stmt = (
        select(WorkOrder)
        .options(joinedload(WorkOrder.equipment), joinedload(WorkOrder.parts).joinedload("part"))
        .order_by(WorkOrder.created_at.desc())
    )
    if status:
        # UI uses Open/Closed; DB has multiple.
        if status.lower() == "open":
            stmt = stmt.where(WorkOrder.status.in_([WorkOrderStatus.OPEN, WorkOrderStatus.ASSIGNED, WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.WAITING_PARTS]))
        elif status.lower() == "closed":
            stmt = stmt.where(WorkOrder.status.in_([WorkOrderStatus.COMPLETED, WorkOrderStatus.CANCELLED]))
        else:
            try:
                stmt = stmt.where(WorkOrder.status == WorkOrderStatus(status))
            except Exception:
                pass

    wos = list(db.scalars(stmt.limit(500)).all())
    out = []
    for wo in wos:
        # Map to UI
        parts = [{"partId": f"P-{p.part.id}", "name": p.part.name, "qty": int(p.qty_required)} for p in wo.parts]
        actions = [{"at": wo.created_at, "by": "system", "note": "Work order created."}]
        closure = None
        if wo.status == WorkOrderStatus.COMPLETED and wo.completed_at:
            closure = {"at": wo.completed_at, "closedBy": wo.assigned_to or "system", "notes": wo.completion_note or ""}
        out.append(
            {
                "id": f"WO-{wo.id}",
                "equipmentId": wo.equipment.asset_tag if wo.equipment else "",
                "alertId": f"AL-{wo.alert_id}" if wo.alert_id else None,
                "title": wo.title,
                "priority": wo.priority.value if hasattr(wo.priority, "value") else str(wo.priority),
                "assignedTo": wo.assigned_to,
                "status": "Closed" if wo.status == WorkOrderStatus.COMPLETED else wo.status.value,
                "createdAt": wo.created_at,
                "dueAt": wo.due_date.isoformat() if wo.due_date else None,
                "actions": actions,
                "parts": parts,
                "closure": closure,
            }
        )
    return out


@router.post("/from-alert", response_model=WorkOrderOut, summary="Create work order from alert", description="Convert an alert into a work order and mark the alert as triaged.")
def create_from_alert(payload: WorkOrderFromAlertCreate, db: Session = Depends(get_db)):
    """Create work order from an alert."""
    if not payload.alertId.startswith("AL-"):
        raise HTTPException(status_code=400, detail="Invalid alert id")
    alert_id = int(payload.alertId.replace("AL-", "", 1))
    alert = db.scalar(select(Alert).options(joinedload(Alert.equipment)).where(Alert.id == alert_id))
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    due_date = _parse_due_date(payload.dueAt)

    # Generate WO number
    wo_number = f"WO-{datetime.utcnow().year}-{alert.id:04d}-{int(datetime.utcnow().timestamp())}"

    wo = WorkOrder(
        alert_id=alert.id,
        equipment_id=alert.equipment_id,
        wo_number=wo_number,
        title=f"Maintain: {alert.equipment.name if alert.equipment else alert.equipment_id} — {alert.title}",
        description=alert.description,
        priority=alert.severity if isinstance(alert.severity, Severity) else Severity.HIGH,
        status=WorkOrderStatus.ASSIGNED,
        assigned_to=payload.assignedTo,
        requested_by="system",
        due_date=due_date,
        started_at=None,
    )
    db.add(wo)

    # Mark alert as acknowledged/triaged in DB
    alert.status = AlertStatus.ACKNOWLEDGED
    alert.acknowledged_at = datetime.utcnow()
    alert.acknowledged_by = payload.assignedTo
    db.add(alert)

    db.commit()
    db.refresh(wo)

    return {
        "id": f"WO-{wo.id}",
        "equipmentId": alert.equipment.asset_tag if alert.equipment else "",
        "alertId": payload.alertId,
        "title": wo.title,
        "priority": wo.priority.value,
        "assignedTo": wo.assigned_to,
        "status": wo.status.value,
        "createdAt": wo.created_at,
        "dueAt": wo.due_date.isoformat() if wo.due_date else None,
        "actions": [{"at": wo.created_at, "by": "system", "note": "Work order created from alert."}],
        "parts": [],
        "closure": None,
    }


@router.patch("/{workOrderId}", response_model=WorkOrderOut, summary="Patch work order", description="Update status/assignment/title/description for a work order.")
def patch_work_order(workOrderId: str, patch: WorkOrderPatch, db: Session = Depends(get_db)):
    """Patch work order fields."""
    if not workOrderId.startswith("WO-"):
        raise HTTPException(status_code=400, detail="Invalid work order id")
    wo_id = int(workOrderId.replace("WO-", "", 1))
    wo = db.scalar(select(WorkOrder).options(joinedload(WorkOrder.equipment), joinedload(WorkOrder.parts).joinedload("part")).where(WorkOrder.id == wo_id))
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found")

    if patch.status:
        try:
            wo.status = WorkOrderStatus(patch.status) if patch.status in WorkOrderStatus.__members__ else WorkOrderStatus.OPEN
        except Exception:
            # Accept UI "Closed"
            if patch.status.lower() == "closed":
                wo.status = WorkOrderStatus.COMPLETED

    if patch.assignedTo is not None:
        wo.assigned_to = patch.assignedTo
    if patch.title is not None:
        wo.title = patch.title
    if patch.description is not None:
        wo.description = patch.description

    db.add(wo)
    db.commit()
    db.refresh(wo)

    parts = [{"partId": f"P-{p.part.id}", "name": p.part.name, "qty": int(p.qty_required)} for p in wo.parts]
    closure = None
    if wo.status == WorkOrderStatus.COMPLETED and wo.completed_at:
        closure = {"at": wo.completed_at, "closedBy": wo.assigned_to or "system", "notes": wo.completion_note or ""}

    return {
        "id": f"WO-{wo.id}",
        "equipmentId": wo.equipment.asset_tag if wo.equipment else "",
        "alertId": f"AL-{wo.alert_id}" if wo.alert_id else None,
        "title": wo.title,
        "priority": wo.priority.value,
        "assignedTo": wo.assigned_to,
        "status": "Closed" if wo.status == WorkOrderStatus.COMPLETED else wo.status.value,
        "createdAt": wo.created_at,
        "dueAt": wo.due_date.isoformat() if wo.due_date else None,
        "actions": [{"at": wo.created_at, "by": "system", "note": "Work order updated."}],
        "parts": parts,
        "closure": closure,
    }


@router.post("/{workOrderId}/close", response_model=WorkOrderOut, summary="Close work order", description="Close a work order and resolve the linked alert if present.")
def close_work_order(workOrderId: str, payload: WorkOrderClose, db: Session = Depends(get_db)):
    """Close work order."""
    if workOrderId != payload.id:
        raise HTTPException(status_code=400, detail="Mismatched id")
    if not workOrderId.startswith("WO-"):
        raise HTTPException(status_code=400, detail="Invalid work order id")

    wo_id = int(workOrderId.replace("WO-", "", 1))
    wo = db.scalar(select(WorkOrder).options(joinedload(WorkOrder.equipment)).where(WorkOrder.id == wo_id))
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found")

    wo.status = WorkOrderStatus.COMPLETED
    wo.completed_at = datetime.utcnow()
    wo.completion_note = payload.notes
    db.add(wo)

    if wo.alert_id:
        alert = db.scalar(select(Alert).where(Alert.id == wo.alert_id))
        if alert:
            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = datetime.utcnow()
            alert.resolved_by = payload.closedBy
            alert.resolution_note = payload.notes
            db.add(alert)

    db.commit()
    db.refresh(wo)

    return {
        "id": f"WO-{wo.id}",
        "equipmentId": wo.equipment.asset_tag if wo.equipment else "",
        "alertId": f"AL-{wo.alert_id}" if wo.alert_id else None,
        "title": wo.title,
        "priority": wo.priority.value,
        "assignedTo": wo.assigned_to,
        "status": "Closed",
        "createdAt": wo.created_at,
        "dueAt": wo.due_date.isoformat() if wo.due_date else None,
        "actions": [{"at": wo.completed_at, "by": payload.closedBy, "note": "Work order closed."}],
        "parts": [],
        "closure": {"at": wo.completed_at, "closedBy": payload.closedBy, "notes": payload.notes},
    }


@router.post("/parts/reserve", response_model=dict, summary="Reserve parts", description="Reserve parts for a work order and decrement inventory when available.")
def reserve_parts(payload: ReservePartsCreate, db: Session = Depends(get_db)):
    """Reserve parts for a work order; matches frontend /parts/reserve but grouped here for convenience."""
    if not payload.workOrderId.startswith("WO-"):
        raise HTTPException(status_code=400, detail="Invalid work order id")
    wo_id = int(payload.workOrderId.replace("WO-", "", 1))
    wo = db.scalar(select(WorkOrder).where(WorkOrder.id == wo_id))
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found")

    items = []
    for it in payload.items:
        part_id_raw = it.get("partId")
        qty = int(it.get("qty", 0))
        if not part_id_raw or not str(part_id_raw).startswith("P-"):
            continue
        part_id = int(str(part_id_raw).replace("P-", "", 1))
        part = db.scalar(select(Part).where(Part.id == part_id))
        if not part:
            raise HTTPException(status_code=404, detail=f"Part not found: {part_id_raw}")
        if qty <= 0:
            continue
        items.append((part, qty))

    reserve_parts_for_work_order(db, wo, items)
    db.commit()
    return {"message": "Parts reservation processed."}
