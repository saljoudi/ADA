from datetime import date
from typing import Any, Optional, Tuple

from .config import ConfigManager


class TemporalEngine:
    """Temporal helpers used by rule evaluation."""

    def __init__(self, config: ConfigManager):
        self.config = config

    def needs_annual_screening(
        self,
        last_date: Optional[date],
        screening_type: str,
        patient,
    ) -> Tuple[bool, Optional[str]]:
        """Return (needs, reason)."""

        if last_date is None:
            return True, "Never performed"

        days_since = (date.today() - last_date).days
        threshold = self.config.get(f"thresholds.annual_{screening_type}_days", 365)

        if screening_type == "eye_exam" and patient.diabetes_complications:
            threshold = 180

        if days_since > threshold:
            return True, f"Last performed {days_since} days ago"
        return False, None

    def is_lab_current(self, lab: Optional[Any], lab_type: str) -> Tuple[bool, Optional[str]]:
        """Validate recency of a lab."""
        if lab is None:
            return False, "No lab result"

        days_old = (date.today() - lab.date).days
        recency = self.config.get(f"thresholds.{lab_type}_recency_days", 90)

        if days_old > recency:
            return False, f"{days_old} days old (max {recency})"
        return True, None

    def medication_duration(self, medication) -> int:
        end = medication.end_date or date.today()
        return (end - medication.start_date).days
