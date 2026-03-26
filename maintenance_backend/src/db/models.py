from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.session import Base
from src.domain.enums import (
    AlertStatus,
    AlertType,
    Criticality,
    EquipmentStatus,
    Severity,
    SourceType,
    WorkOrderPartStatus,
    WorkOrderStatus,
)


class Plant(Base):
    __tablename__ = "plants"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, server_default="UTC")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())

    areas: Mapped[list["Area"]] = relationship(back_populates="plant")
    equipment: Mapped[list["Equipment"]] = relationship(back_populates="plant")


class Area(Base):
    __tablename__ = "areas"
    __table_args__ = (UniqueConstraint("plant_id", "code", name="uq_area"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    plant_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("plants.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())

    plant: Mapped["Plant"] = relationship(back_populates="areas")
    equipment: Mapped[list["Equipment"]] = relationship(back_populates="area")


class Equipment(Base):
    __tablename__ = "equipment"
    __table_args__ = (
        Index("idx_equipment_plant", "plant_id"),
        Index("idx_equipment_area", "area_id"),
        Index("idx_equipment_type", "equipment_type"),
        Index("idx_equipment_status", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    plant_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("plants.id", ondelete="RESTRICT"), nullable=False)
    area_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("areas.id", ondelete="SET NULL"))
    asset_tag: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    equipment_type: Mapped[str] = mapped_column(String(80), nullable=False)
    manufacturer: Mapped[Optional[str]] = mapped_column(String(120))
    model: Mapped[Optional[str]] = mapped_column(String(120))
    serial_number: Mapped[Optional[str]] = mapped_column(String(120))
    criticality: Mapped[Criticality] = mapped_column(Enum(Criticality), nullable=False, server_default=Criticality.MEDIUM.value)
    status: Mapped[EquipmentStatus] = mapped_column(Enum(EquipmentStatus), nullable=False, server_default=EquipmentStatus.ACTIVE.value)
    install_date: Mapped[Optional[date]] = mapped_column(Date)
    last_service_date: Mapped[Optional[date]] = mapped_column(Date)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )

    plant: Mapped["Plant"] = relationship(back_populates="equipment")
    area: Mapped[Optional["Area"]] = relationship(back_populates="equipment")
    components: Mapped[list["EquipmentComponent"]] = relationship(back_populates="equipment")
    parameters: Mapped[list["EquipmentParameter"]] = relationship(back_populates="equipment")
    readings: Mapped[list["EquipmentReading"]] = relationship(back_populates="equipment")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="equipment")
    work_orders: Mapped[list["WorkOrder"]] = relationship(back_populates="equipment")


class EquipmentComponent(Base):
    __tablename__ = "equipment_components"
    __table_args__ = (
        UniqueConstraint("equipment_id", "name", name="uq_component"),
        Index("idx_components_equipment", "equipment_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    equipment_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("equipment.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    component_type: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())

    equipment: Mapped["Equipment"] = relationship(back_populates="components")
    parameters: Mapped[list["EquipmentParameter"]] = relationship(back_populates="component")
    readings: Mapped[list["EquipmentReading"]] = relationship(back_populates="component")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="component")


class ParameterCatalog(Base):
    __tablename__ = "parameter_catalog"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    unit: Mapped[Optional[str]] = mapped_column(String(32))
    description: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())

    equipment_parameters: Mapped[list["EquipmentParameter"]] = relationship(back_populates="parameter")
    readings: Mapped[list["EquipmentReading"]] = relationship(back_populates="parameter")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="parameter")


class EquipmentParameter(Base):
    __tablename__ = "equipment_parameters"
    __table_args__ = (
        UniqueConstraint("equipment_id", "component_id", "parameter_id", name="uq_equipment_param"),
        Index("idx_eqparam_equipment", "equipment_id"),
        Index("idx_eqparam_parameter", "parameter_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    equipment_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("equipment.id", ondelete="CASCADE"), nullable=False)
    component_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("equipment_components.id", ondelete="SET NULL")
    )
    parameter_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("parameter_catalog.id", ondelete="RESTRICT"), nullable=False
    )
    source: Mapped[SourceType] = mapped_column(Enum(SourceType), nullable=False, server_default=SourceType.SENSOR.value)
    is_enabled: Mapped[bool] = mapped_column(Integer, nullable=False, server_default="1")

    warn_low: Mapped[Optional[float]] = mapped_column(Numeric(14, 4))
    warn_high: Mapped[Optional[float]] = mapped_column(Numeric(14, 4))
    alarm_low: Mapped[Optional[float]] = mapped_column(Numeric(14, 4))
    alarm_high: Mapped[Optional[float]] = mapped_column(Numeric(14, 4))
    expected_low: Mapped[Optional[float]] = mapped_column(Numeric(14, 4))
    expected_high: Mapped[Optional[float]] = mapped_column(Numeric(14, 4))
    sample_interval_seconds: Mapped[Optional[int]] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )

    equipment: Mapped["Equipment"] = relationship(back_populates="parameters")
    component: Mapped[Optional["EquipmentComponent"]] = relationship(back_populates="parameters")
    parameter: Mapped["ParameterCatalog"] = relationship(back_populates="equipment_parameters")


class EquipmentReading(Base):
    __tablename__ = "equipment_readings"
    __table_args__ = (
        Index("idx_readings_equipment_time", "equipment_id", "recorded_at"),
        Index("idx_readings_param_time", "parameter_id", "recorded_at"),
        Index("idx_readings_component", "component_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    equipment_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("equipment.id", ondelete="CASCADE"), nullable=False)
    component_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("equipment_components.id", ondelete="SET NULL")
    )
    parameter_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("parameter_catalog.id", ondelete="RESTRICT"), nullable=False
    )
    recorded_at: Mapped[datetime] = mapped_column(DateTime(3), nullable=False)
    value: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    source: Mapped[SourceType] = mapped_column(Enum(SourceType), nullable=False, server_default=SourceType.SENSOR.value)
    recorded_by: Mapped[Optional[str]] = mapped_column(String(120))
    note: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())

    equipment: Mapped["Equipment"] = relationship(back_populates="readings")
    component: Mapped[Optional["EquipmentComponent"]] = relationship(back_populates="readings")
    parameter: Mapped["ParameterCatalog"] = relationship(back_populates="readings")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="reading")


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        Index("idx_alerts_status", "status"),
        Index("idx_alerts_equipment_time", "equipment_id", "detected_at"),
        Index("idx_alerts_severity", "severity"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    equipment_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("equipment.id", ondelete="CASCADE"), nullable=False)
    component_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("equipment_components.id", ondelete="SET NULL")
    )
    parameter_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("parameter_catalog.id", ondelete="RESTRICT"), nullable=False
    )
    reading_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("equipment_readings.id", ondelete="SET NULL")
    )

    alert_type: Mapped[AlertType] = mapped_column(Enum(AlertType), nullable=False)
    severity: Mapped[Severity] = mapped_column(Enum(Severity), nullable=False)
    status: Mapped[AlertStatus] = mapped_column(Enum(AlertStatus), nullable=False, server_default=AlertStatus.OPEN.value)

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    detected_at: Mapped[datetime] = mapped_column(DateTime(3), nullable=False)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(3))
    acknowledged_by: Mapped[Optional[str]] = mapped_column(String(120))
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(3))
    resolved_by: Mapped[Optional[str]] = mapped_column(String(120))
    resolution_note: Mapped[Optional[str]] = mapped_column(Text)

    priority_score: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )

    equipment: Mapped["Equipment"] = relationship(back_populates="alerts")
    component: Mapped[Optional["EquipmentComponent"]] = relationship(back_populates="alerts")
    parameter: Mapped["ParameterCatalog"] = relationship(back_populates="alerts")
    reading: Mapped[Optional["EquipmentReading"]] = relationship(back_populates="alerts")
    work_orders: Mapped[list["WorkOrder"]] = relationship(back_populates="alert")


class WorkOrder(Base):
    __tablename__ = "work_orders"
    __table_args__ = (
        Index("idx_wo_status", "status"),
        Index("idx_wo_priority", "priority"),
        Index("idx_wo_equipment", "equipment_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    alert_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("alerts.id", ondelete="SET NULL"))
    equipment_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("equipment.id", ondelete="CASCADE"), nullable=False)
    wo_number: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    priority: Mapped[Severity] = mapped_column(Enum(Severity), nullable=False, server_default=Severity.MEDIUM.value)
    status: Mapped[WorkOrderStatus] = mapped_column(Enum(WorkOrderStatus), nullable=False, server_default=WorkOrderStatus.OPEN.value)
    requested_by: Mapped[Optional[str]] = mapped_column(String(120))
    assigned_to: Mapped[Optional[str]] = mapped_column(String(120))

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
    due_date: Mapped[Optional[date]] = mapped_column(Date)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(3))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(3))
    completion_note: Mapped[Optional[str]] = mapped_column(Text)

    equipment: Mapped["Equipment"] = relationship(back_populates="work_orders")
    alert: Mapped[Optional["Alert"]] = relationship(back_populates="work_orders")
    parts: Mapped[list["WorkOrderPart"]] = relationship(back_populates="work_order")


class Part(Base):
    __tablename__ = "parts"
    __table_args__ = (Index("idx_parts_stock", "stock_qty"), Index("idx_parts_reorder", "reorder_point"))

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    part_number: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255))
    unit_cost: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    stock_qty: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    reorder_point: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    supplier: Mapped[Optional[str]] = mapped_column(String(160))
    lead_time_days: Mapped[Optional[int]] = mapped_column(Integer)
    location: Mapped[Optional[str]] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )

    work_order_parts: Mapped[list["WorkOrderPart"]] = relationship(back_populates="part")


class WorkOrderPart(Base):
    __tablename__ = "work_order_parts"
    __table_args__ = (
        UniqueConstraint("work_order_id", "part_id", name="uq_wo_part"),
        Index("idx_wop_wo", "work_order_id"),
        Index("idx_wop_part", "part_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    work_order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("work_orders.id", ondelete="CASCADE"), nullable=False)
    part_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("parts.id", ondelete="RESTRICT"), nullable=False)
    qty_required: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    qty_reserved: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    status: Mapped[WorkOrderPartStatus] = mapped_column(
        Enum(WorkOrderPartStatus), nullable=False, server_default=WorkOrderPartStatus.REQUIRED.value
    )
    note: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())

    work_order: Mapped["WorkOrder"] = relationship(back_populates="parts")
    part: Mapped["Part"] = relationship(back_populates="work_order_parts")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("idx_audit_entity", "entity_type", "entity_id"), Index("idx_audit_time", "occurred_at"))

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    actor: Mapped[Optional[str]] = mapped_column(String(120))
    details: Mapped[Optional[dict]] = mapped_column(JSON)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(3), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
