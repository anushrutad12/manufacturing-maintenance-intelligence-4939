from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import and_, desc, select
from sqlalchemy.orm import Session

from src.db.models import (
    Alert,
    Equipment,
    EquipmentParameter,
    EquipmentReading,
    ParameterCatalog,
    Part,
    WorkOrder,
    WorkOrderPart,
)
from src.domain.enums import AlertStatus, Severity, SourceType, WorkOrderPartStatus, WorkOrderStatus


def _utcnow_naive() -> datetime:
    """Return naive UTC datetime compatible with MySQL DATETIME."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_equipment_by_asset_tag(db: Session, asset_tag: str) -> Optional[Equipment]:
    return db.scalar(select(Equipment).where(Equipment.asset_tag == asset_tag))


def list_equipment(db: Session) -> list[Equipment]:
    return list(db.scalars(select(Equipment).order_by(Equipment.id.desc())).all())


def ensure_parameter_catalog(db: Session, name: str, unit: Optional[str] = None) -> ParameterCatalog:
    existing = db.scalar(select(ParameterCatalog).where(ParameterCatalog.name == name))
    if existing:
        # Update unit opportunistically if provided
        if unit and (existing.unit is None or existing.unit == ""):
            existing.unit = unit
            db.add(existing)
            db.flush()
        return existing
    item = ParameterCatalog(name=name, unit=unit)
    db.add(item)
    db.flush()
    return item


def get_equipment_parameter(
    db: Session, equipment_id: int, parameter_id: int, component_id: Optional[int] = None
) -> Optional[EquipmentParameter]:
    return db.scalar(
        select(EquipmentParameter).where(
            and_(
                EquipmentParameter.equipment_id == equipment_id,
                EquipmentParameter.parameter_id == parameter_id,
                EquipmentParameter.component_id.is_(component_id) if component_id is None else EquipmentParameter.component_id == component_id,
            )
        )
    )


def list_readings(db: Session, equipment_asset_tag: Optional[str] = None, limit: int = 200) -> list[EquipmentReading]:
    stmt = select(EquipmentReading).order_by(desc(EquipmentReading.recorded_at)).limit(limit)
    if equipment_asset_tag:
        eq = get_equipment_by_asset_tag(db, equipment_asset_tag)
        if not eq:
            return []
        stmt = stmt.where(EquipmentReading.equipment_id == eq.id)
    return list(db.scalars(stmt).all())


def list_alerts(
    db: Session, equipment_asset_tag: Optional[str] = None, status: Optional[str] = None, limit: int = 200
) -> list[Alert]:
    stmt = select(Alert).order_by(desc(Alert.detected_at)).limit(limit)
    if equipment_asset_tag:
        eq = get_equipment_by_asset_tag(db, equipment_asset_tag)
        if not eq:
            return []
        stmt = stmt.where(Alert.equipment_id == eq.id)
    if status:
        # Frontend uses Open/Triaged/Closed; map to DB statuses.
        if status.lower() == "open":
            stmt = stmt.where(Alert.status.in_([AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED, AlertStatus.IN_PROGRESS]))
        elif status.lower() == "closed":
            stmt = stmt.where(Alert.status.in_([AlertStatus.RESOLVED, AlertStatus.DISMISSED]))
        else:
            # pass-through if matches enum name
            try:
                stmt = stmt.where(Alert.status == AlertStatus(status))
            except Exception:
                pass
    return list(db.scalars(stmt).all())


def list_work_orders(db: Session, status: Optional[str] = None, limit: int = 200) -> list[WorkOrder]:
    stmt = select(WorkOrder).order_by(desc(WorkOrder.created_at)).limit(limit)
    if status:
        try:
            stmt = stmt.where(WorkOrder.status == WorkOrderStatus(status))
        except Exception:
            pass
    return list(db.scalars(stmt).all())


def get_work_order_by_number(db: Session, wo_number: str) -> Optional[WorkOrder]:
    return db.scalar(select(WorkOrder).where(WorkOrder.wo_number == wo_number))


def get_work_order(db: Session, wo_id: int) -> Optional[WorkOrder]:
    return db.scalar(select(WorkOrder).where(WorkOrder.id == wo_id))


def list_parts(db: Session) -> list[Part]:
    return list(db.scalars(select(Part).order_by(Part.name.asc())).all())


def reserve_parts_for_work_order(
    db: Session, work_order: WorkOrder, items: list[tuple[Part, int]]
) -> list[WorkOrderPart]:
    out = []
    for part, qty in items:
        qty = int(qty)
        wop = db.scalar(
            select(WorkOrderPart).where(and_(WorkOrderPart.work_order_id == work_order.id, WorkOrderPart.part_id == part.id))
        )
        if not wop:
            wop = WorkOrderPart(work_order_id=work_order.id, part_id=part.id, qty_required=qty)
        else:
            wop.qty_required = max(wop.qty_required, qty)

        if part.stock_qty >= qty:
            part.stock_qty -= qty
            wop.qty_reserved = qty
            wop.status = WorkOrderPartStatus.RESERVED
        else:
            wop.qty_reserved = 0
            wop.status = WorkOrderPartStatus.BACKORDERED

        db.add(part)
        db.add(wop)
        out.append(wop)
    db.flush()
    return out


def count_open_alerts_by_equipment(db: Session, equipment_id: int) -> list[Severity]:
    stmt = select(Alert.severity).where(
        and_(
            Alert.equipment_id == equipment_id,
            Alert.status.in_([AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED, AlertStatus.IN_PROGRESS]),
        )
    )
    return list(db.scalars(stmt).all())


def create_reading(
    db: Session,
    *,
    equipment: Equipment,
    parameter: ParameterCatalog,
    value: float,
    unit: Optional[str],
    recorded_by: Optional[str],
    source: SourceType,
    note: Optional[str],
    recorded_at: Optional[datetime] = None,
) -> EquipmentReading:
    r = EquipmentReading(
        equipment_id=equipment.id,
        component_id=None,
        parameter_id=parameter.id,
        recorded_at=recorded_at or _utcnow_naive(),
        value=value,
        source=source,
        recorded_by=recorded_by,
        note=note,
    )
    db.add(r)
    db.flush()
    return r
