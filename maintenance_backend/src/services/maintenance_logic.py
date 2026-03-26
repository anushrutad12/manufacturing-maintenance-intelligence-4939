from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from src.domain.enums import AlertType, Criticality, Severity


@dataclass(frozen=True)
class ThresholdEval:
    """Result of evaluating a reading against configured thresholds."""

    level: str  # ok|warn|alarm
    alert_type: Optional[AlertType] = None
    severity: Optional[Severity] = None
    score: int = 0
    title: str = ""
    description: str = ""


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def evaluate_thresholds(
    *,
    parameter_name: str,
    value: float,
    unit: Optional[str],
    warn_high: Optional[float],
    alarm_high: Optional[float],
    warn_low: Optional[float],
    alarm_low: Optional[float],
    equipment_criticality: Criticality,
) -> ThresholdEval:
    """Evaluate a value against configured high/low warn/alarm thresholds."""
    breached = []

    if alarm_high is not None and value >= float(alarm_high):
        breached.append(("alarm_high", float(alarm_high)))
    if warn_high is not None and value >= float(warn_high):
        breached.append(("warn_high", float(warn_high)))
    if alarm_low is not None and value <= float(alarm_low):
        breached.append(("alarm_low", float(alarm_low)))
    if warn_low is not None and value <= float(warn_low):
        breached.append(("warn_low", float(warn_low)))

    if not breached:
        return ThresholdEval(level="ok")

    # Determine band
    is_alarm = any(k.startswith("alarm_") for k, _ in breached)
    alert_type = AlertType.ALARM if is_alarm else AlertType.WARN

    # Determine severity baseline
    base_sev = Severity.MEDIUM if alert_type == AlertType.WARN else Severity.HIGH

    # Escalate with equipment criticality
    if equipment_criticality in (Criticality.HIGH, Criticality.CRITICAL) and base_sev == Severity.HIGH:
        base_sev = Severity.CRITICAL

    # Score 0-100: alarm starts high; warn mid.
    score = 55 if alert_type == AlertType.WARN else 75

    # Add magnitude factor
    # Use worst relevant threshold to scale.
    worst = breached[0]
    for b in breached[1:]:
        if b[0].startswith("alarm_") and not worst[0].startswith("alarm_"):
            worst = b

    _, threshold_value = worst
    if threshold_value != 0:
        magnitude = abs((value - threshold_value) / threshold_value)
        score += int(min(25, magnitude * 100))

    # Escalate by criticality
    if equipment_criticality == Criticality.CRITICAL:
        score += 10
    elif equipment_criticality == Criticality.HIGH:
        score += 5

    score = max(0, min(100, score))

    # Simple title/description
    direction = "above" if "high" in worst[0] else "below"
    band = "alarm" if alert_type == AlertType.ALARM else "warning"
    title = f"{parameter_name} {direction} {band} limit"
    u = f" {unit}" if unit else ""
    description = f"{parameter_name} reading {value}{u} is {direction} the configured {band} threshold ({threshold_value}{u})."

    return ThresholdEval(
        level="alarm" if is_alarm else "warn",
        alert_type=alert_type,
        severity=Severity.CRITICAL if score >= 90 else (Severity.HIGH if score >= 70 else base_sev),
        score=score,
        title=title,
        description=description,
    )


def derive_equipment_health_label(open_alert_severities: list[Severity]) -> str:
    """Derive UI-facing health label from open alert severities."""
    if any(s == Severity.CRITICAL for s in open_alert_severities):
        return "Critical"
    if any(s in (Severity.HIGH, Severity.MEDIUM) for s in open_alert_severities):
        return "At Risk"
    return "Healthy"
