from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.schemas.equipment import EquipmentCreate, EquipmentOut
from src.db.session import get_db
from src.services.maintenance_service import create_equipment_from_ui, list_equipment_ui

router = APIRouter(prefix="/equipment", tags=["equipment"])


@router.get("", response_model=list[EquipmentOut], summary="List equipment", description="List registered equipment.")
def get_equipment(db: Session = Depends(get_db)):
    """List equipment for the React UI."""
    return list_equipment_ui(db)


@router.post("", response_model=EquipmentOut, summary="Create equipment", description="Register new equipment and thresholds.")
def post_equipment(payload: EquipmentCreate, db: Session = Depends(get_db)):
    """Create equipment based on the UI payload shape."""
    try:
        return create_equipment_from_ui(db, payload.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
