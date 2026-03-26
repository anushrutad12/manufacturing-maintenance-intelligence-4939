from enum import Enum


class Criticality(str, Enum):
    """Equipment criticality."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class EquipmentStatus(str, Enum):
    """Lifecycle status for equipment."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    DECOMMISSIONED = "DECOMMISSIONED"


class SourceType(str, Enum):
    """Origin of a reading."""

    SENSOR = "SENSOR"
    OPERATOR = "OPERATOR"


class AlertType(str, Enum):
    """Alert type based on threshold band."""

    WARN = "WARN"
    ALARM = "ALARM"


class Severity(str, Enum):
    """Alert/work order severity/priority."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertStatus(str, Enum):
    """Alert lifecycle."""

    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class WorkOrderStatus(str, Enum):
    """Work order lifecycle."""

    DRAFT = "DRAFT"
    OPEN = "OPEN"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING_PARTS = "WAITING_PARTS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class WorkOrderPartStatus(str, Enum):
    """Status of parts against a work order."""

    REQUIRED = "REQUIRED"
    RESERVED = "RESERVED"
    ISSUED = "ISSUED"
    BACKORDERED = "BACKORDERED"
