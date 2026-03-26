from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from src.db.models import Alert, Equipment, EquipmentParameter, WorkOrder
from src.domain.enums import AlertStatus, Severity, SourceType, WorkOrderStatus
from src.services.maintenance_logic import derive_equipment_health_label, evaluate_thresholds
from src.services.repositories import (
    _utcnow_naive,
    count_open_alerts_by_equipment,
    create_reading,
    ensure_parameter_catalog,
    get_equipment_by_asset_tag,
    list_equipment,
)


def _ui_id(prefix: str, numeric_id: int) -> str:
    return f"{prefix}{numeric_id}"


def _parse_ui_id(prefix: str, ui_id: str) -> int:
    if not ui_id.startswith(prefix):
        raise ValueError("Invalid id")
    return int(ui_id[len(prefix) :])


def _severity_to_ui(sev: Severity) -> str:
    return sev.value


def _alert_status_to_ui(status: AlertStatus) -> str:
    # UI in mocks uses Open/Triaged/Closed; map DB statuses.
    if status in (AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED, AlertStatus.IN_PROGRESS):
        return "Open" if status == AlertStatus.OPEN else "Triaged"
    return "Closed"


def _ui_to_alert_status(s: str) -> AlertStatus:
    return AlertStatus(s)


def equipment_to_ui(db: Session, eq: Equipment) -> dict:
    severities = count_open_alerts_by_equipment(db, eq.id)
    health = derive_equipment_health_label(severities)

    # Build thresholds map parameter name -> {warn, danger, unit}
    th_map: Dict[str, Any] = {}
    for ep in eq.parameters:
        if not ep.is_enabled:
            continue
        p_name = ep.parameter.name
        unit = ep.parameter.unit
        warn = ep.warn_high if ep.warn_high is not None else ep.expected_high
        danger = ep.alarm_high if ep.alarm_high is not None else ep.warn_high
        if warn is None or danger is None:
            continue
        th_map[p_name] = {"warn": float(warn), "danger": float(danger), "unit": unit}

    return {
        "id": eq.asset_tag,
        "name": eq.name,
        "area": eq.area.code if eq.area else "",
        "model": eq.model,
        "thresholds": th_map,
        "status": health,
        "updatedAt": eq.updated_at,
        "dbId": eq.id,
    }


def reading_to_ui(reading) -> dict:
    return {
        "id": _ui_id("LOG-", reading.id),
        "equipmentId": reading.equipment.asset_tag if reading.equipment else "",
        "parameter": reading.parameter.name if reading.parameter else "",
        "value": float(reading.value),
        "unit": reading.parameter.unit if reading.parameter else None,
        "recordedAt": reading.recorded_at,
        "recordedBy": "sensor" if reading.source == SourceType.SENSOR else "operator",
        "note": reading.note or "",
    }


def alert_to_ui(alert: Alert) -> dict:
    return {
        "id": _ui_id("AL-", alert.id),
        "equipmentId": alert.equipment.asset_tag if alert.equipment else "",
        "title": alert.title,
        "parameter": alert.parameter.name if alert.parameter else "",
        "value": float(alert.reading.value) if alert.reading else 0.0,
        "unit": alert.parameter.unit if alert.parameter else None,
        "severity": _severity_to_ui(alert.severity),
        "score": int(alert.priority_score),
        "status": _alert_status_to_ui(alert.status),
        "createdAt": alert.detected_at,
        "description": alert.description or "",
    }


def work_order_to_ui(db: Session, wo: WorkOrder) -> dict:
    parts = []
    for p in wo.parts:
        parts.append({"partId": _ui_id("P-", p.part.id), "name": p.part.name, "qty": int(p.qty_required)})

    actions = [{"at": wo.created_at, "by": "system", "note": "Work order created."}]
    if wo.status:
        actions.insert(0, {"at": wo.created_at, "by": "system", "note": f"Status set to {wo.status.value}."})

    closure = None
    if wo.status == WorkOrderStatus.COMPLETED and wo.completed_at:
        closure = {"at": wo.completed_at, "closedBy": wo.assigned_to or "system", "notes": wo.completion_note or ""}

    return {
        "id": _ui_id("WO-", wo.id),
        "equipmentId": wo.equipment.asset_tag if wo.equipment else "",
        "alertId": _ui_id("AL-", wo.alert_id) if wo.alert_id else None,
        "title": wo.title,
        "priority": wo.priority.value,
        "assignedTo": wo.assigned_to,
        "status": "Closed" if wo.status == WorkOrderStatus.COMPLETED else wo.status.value,
        "createdAt": wo.created_at,
        "dueAt": wo.due_date.isoformat() if wo.due_date else None,
        "actions": actions,
        "parts": parts,
        "closure": closure,
    }


# PUBLIC_INTERFACE
def create_equipment_from_ui(db: Session, payload: dict) -> dict:
    """Create equipment and parameter thresholds from UI payload."""
    asset_tag = payload.get("id") or payload["name"].upper().replace(" ", "-")[:20]
    eq = get_equipment_by_asset_tag(db, asset_tag)
    if eq:
        raise ValueError("Equipment already exists with id/asset tag")

    # Resolve area by code or name (simple lookup); fall back to NULL area.
    area_code = payload.get("area") or ""
    area = None
    if area_code:
        from src.db.models import Area

        area = db.scalar(select(Area).where(Area.code == area_code))
        if not area:
            area = db.scalar(select(Area).where(Area.name == area_code))

    # Default plant_id=1 (seeded)
    eq = Equipment(
        plant_id=1,
        area_id=area.id if area else None,
        asset_tag=asset_tag,
        name=payload["name"],
        equipment_type=payload.get("equipment_type") or "Equipment",
        manufacturer=payload.get("manufacturer"),
        model=payload.get("model"),
        serial_number=payload.get("serial_number"),
    )
    db.add(eq)
    db.flush()

    thresholds = payload.get("thresholds") or {}
    for param_name, band in thresholds.items():
        if not isinstance(band, dict):
            continue
        warn = band.get("warn")
        danger = band.get("danger")
        unit = band.get("unit")
        if warn is None or danger is None:
            continue
        p = ensure_parameter_catalog(db, param_name, unit=unit)
        ep = EquipmentParameter(
            equipment_id=eq.id,
            component_id=None,
            parameter_id=p.id,
            source=SourceType.SENSOR,
            is_enabled=True,
            warn_high=float(warn),
            alarm_high=float(danger),
        )
        db.add(ep)

    db.flush()
    db.refresh(eq)
    # load relationships
    eq.parameters
    return equipment_to_ui(db, eq)


# PUBLIC_INTERFACE
def list_equipment_ui(db: Session) -> list[dict]:
    """List equipment as UI-friendly objects."""
    items = list_equipment(db)
    # Ensure relationships loaded
    for e in items:
        e.parameters
        e.area
    return [equipment_to_ui(db, e) for e in items]


# PUBLIC_INTERFACE
def create_log_and_alerts(db: Session, payload: dict) -> Tuple[dict, Optional[dict]]:
    """Create a log (reading). If thresholds breached, create an alert and return it too."""
    eq = get_equipment_by_asset_tag(db, payload["equipmentId"])
    if not eq:
        raise ValueError("Equipment not found")

    parameter_name = payload["parameter"]
    unit = payload.get("unit")
    parameter = ensure_parameter_catalog(db, parameter_name, unit=unit)

    # Find configured thresholds for equipment (component-less for UI)
    eq_param = db.scalar(
        select(EquipmentParameter).where(
            and_(
                EquipmentParameter.equipment_id == eq.id,
                EquipmentParameter.parameter_id == parameter.id,
                EquipmentParameter.component_id.is_(None),
            )
        )
    )

    source = SourceType.SENSOR if str(payload.get("recordedBy", "sensor")).lower() == "sensor" else SourceType.OPERATOR
    reading = create_reading(
        db,
        equipment=eq,
        parameter=parameter,
        value=float(payload["value"]),
        unit=unit,
        recorded_by=None if source == SourceType.SENSOR else "operator",
        source=source,
        note=payload.get("note"),
        recorded_at=_utcnow_naive(),
    )

    # Attach relationships for UI projection
    db.refresh(reading)
    reading.equipment = eq
    reading.parameter = parameter

    created_alert_ui = None
    if eq_param and eq_param.is_enabled:
        eval_res = evaluate_thresholds(
            parameter_name=parameter_name,
            value=float(payload["value"]),
            unit=parameter.unit or unit,
            warn_high=float(eq_param.warn_high) if eq_param.warn_high is not None else None,
            alarm_high=float(eq_param.alarm_high) if eq_param.alarm_high is not None else None,
            warn_low=float(eq_param.warn_low) if eq_param.warn_low is not None else None,
            alarm_low=float(eq_param.alarm_low) if eq_param.alarm_low is not None else None,
            equipment_criticality=eq.criticality,
        )
        if eval_res.level in ("warn", "alarm"):
            alert = Alert(
                equipment_id=eq.id,
                component_id=None,
                parameter_id=parameter.id,
                reading_id=reading.id,
                alert_type=eval_res.alert_type,
                severity=eval_res.severity,
                status=AlertStatus.OPEN,
                title=eval_res.title,
                description=eval_res.description,
                detected_at=reading.recorded_at,
                priority_score=eval_res.score,
            )
            db.add(alert)
            db.flush()
            db.refresh(alert)
            alert.equipment = eq
            alert.parameter = parameter
            alert.reading = reading
            created_alert_ui = alert_to_ui(alert)

    return reading_to_ui(reading), created_alert_ui
