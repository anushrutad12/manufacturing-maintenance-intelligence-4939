from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from src.api.schemas.alerts import AlertOut, AlertStatusPatch
from src.db.models import Alert
from src.db.session import get_db
from src.domain.enums import AlertStatus

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertOut], summary="List alerts", description="List alerts. Supports filtering by equipmentId and status.")
def list_alerts(
    equipmentId: str | None = Query(default=None, description="Equipment external id (asset tag)"),
    status: str | None = Query(default=None, description='Status filter (UI uses "Open" or "Closed")'),
    db: Session = Depends(get_db),
):
    """List alerts for UI."""
    stmt = (
        select(Alert)
        .options(joinedload(Alert.equipment), joinedload(Alert.parameter), joinedload(Alert.reading))
        .order_by(Alert.detected_at.desc())
    )
    if equipmentId:
        from src.db.models import Equipment

        stmt = stmt.join(Equipment).where(Equipment.asset_tag == equipmentId)

    if status:
        if status.lower() == "open":
            stmt = stmt.where(Alert.status.in_([AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED, AlertStatus.IN_PROGRESS]))
        elif status.lower() == "closed":
            stmt = stmt.where(Alert.status.in_([AlertStatus.RESOLVED, AlertStatus.DISMISSED]))

    alerts = list(db.scalars(stmt.limit(500)).all())
    out = []
    for a in alerts:
        out.append(
            {
                "id": f"AL-{a.id}",
                "equipmentId": a.equipment.asset_tag if a.equipment else "",
                "title": a.title,
                "parameter": a.parameter.name if a.parameter else "",
                "value": float(a.reading.value) if a.reading else 0.0,
                "unit": a.parameter.unit if a.parameter else None,
                "severity": a.severity.value,
                "score": int(a.priority_score),
                "status": "Open" if a.status == AlertStatus.OPEN else ("Triaged" if a.status in (AlertStatus.ACKNOWLEDGED, AlertStatus.IN_PROGRESS) else "Closed"),
                "createdAt": a.detected_at,
                "description": a.description or "",
            }
        )
    return out


@router.patch("/{alertId}", response_model=AlertOut, summary="Update alert status", description="Update an alert lifecycle status.")
def patch_alert(alertId: str, patch: AlertStatusPatch, db: Session = Depends(get_db)):
    """Patch an alert status."""
    if not alertId.startswith("AL-"):
        raise HTTPException(status_code=400, detail="Invalid alert id")
    numeric_id = int(alertId.replace("AL-", "", 1))
    alert = db.scalar(
        select(Alert).options(joinedload(Alert.equipment), joinedload(Alert.parameter), joinedload(Alert.reading)).where(Alert.id == numeric_id)
    )
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    try:
        alert.status = AlertStatus(patch.status)
        db.add(alert)
        db.commit()
        db.refresh(alert)
        return {
            "id": f"AL-{alert.id}",
            "equipmentId": alert.equipment.asset_tag if alert.equipment else "",
            "title": alert.title,
            "parameter": alert.parameter.name if alert.parameter else "",
            "value": float(alert.reading.value) if alert.reading else 0.0,
            "unit": alert.parameter.unit if alert.parameter else None,
            "severity": alert.severity.value,
            "score": int(alert.priority_score),
            "status": "Open" if alert.status == AlertStatus.OPEN else ("Triaged" if alert.status in (AlertStatus.ACKNOWLEDGED, AlertStatus.IN_PROGRESS) else "Closed"),
            "createdAt": alert.detected_at,
            "description": alert.description or "",
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid status") from e
