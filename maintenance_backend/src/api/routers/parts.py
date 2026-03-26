from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.schemas.work_orders import PartOut, ReservePartsCreate
from src.db.models import Part, WorkOrder
from src.db.session import get_db
from src.services.repositories import reserve_parts_for_work_order

router = APIRouter(prefix="/parts", tags=["parts"])


@router.get("", response_model=list[PartOut], summary="List parts", description="List spare parts and current stock.")
def list_parts(db: Session = Depends(get_db)):
    """List parts."""
    parts = list(db.scalars(select(Part).order_by(Part.name.asc())).all())
    return [{"id": f"P-{p.id}", "name": p.name, "stock": int(p.stock_qty)} for p in parts]


@router.post("/reserve", response_model=dict, summary="Reserve parts for work order", description="Reserve parts and decrement stock if available.")
def reserve_parts(payload: ReservePartsCreate, db: Session = Depends(get_db)):
    """Reserve parts for a work order."""
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
        items.append((part, qty))

    reserve_parts_for_work_order(db, wo, items)
    db.commit()
    return {"message": "Parts reserved."}
