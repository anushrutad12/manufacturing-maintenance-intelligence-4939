from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from src.api.schemas.logs import LogCreate, LogOut
from src.db.models import EquipmentReading
from src.db.session import get_db
from src.services.maintenance_service import create_log_and_alerts

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("", response_model=list[LogOut], summary="List logs", description="List parameter logs/readings. Optional filter by equipmentId.")
def list_logs(
    equipmentId: str | None = Query(default=None, description="Equipment external id (asset tag)"),
    db: Session = Depends(get_db),
):
    """List readings for UI consumption."""
    stmt = select(EquipmentReading).options(joinedload(EquipmentReading.equipment), joinedload(EquipmentReading.parameter)).order_by(
        EquipmentReading.recorded_at.desc()
    )
    if equipmentId:
        # join through relationship already; filter by asset tag
        from src.db.models import Equipment

        stmt = stmt.join(Equipment).where(Equipment.asset_tag == equipmentId)

    readings = list(db.scalars(stmt.limit(500)).all())
    out = []
    for r in readings:
        out.append(
            {
                "id": f"LOG-{r.id}",
                "equipmentId": r.equipment.asset_tag if r.equipment else "",
                "parameter": r.parameter.name if r.parameter else "",
                "value": float(r.value),
                "unit": r.parameter.unit if r.parameter else None,
                "recordedAt": r.recorded_at,
                "recordedBy": "sensor" if r.source.value == "SENSOR" else "operator",
                "note": r.note or "",
            }
        )
    return out


@router.post("", response_model=LogOut, summary="Create log", description="Create a new reading/log; auto-creates an alert if thresholds are breached.")
def create_log(payload: LogCreate, db: Session = Depends(get_db)):
    """Create log and possibly generate an alert if thresholds are breached."""
    try:
        reading_ui, _alert_ui = create_log_and_alerts(db, payload.model_dump())
        db.commit()
        return reading_ui
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create log") from e
