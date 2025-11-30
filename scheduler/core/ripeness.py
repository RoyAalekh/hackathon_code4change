"""Case ripeness classification for intelligent scheduling.

Ripe cases are ready for substantive judicial time.
Unripe cases have bottlenecks (summons, dependencies, parties, documents).

Based on analysis of historical PurposeOfHearing patterns (see scripts/analyze_ripeness_patterns.py).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scheduler.core.case import Case


class RipenessStatus(Enum):
    """Status indicating whether a case is ready for hearing."""

    RIPE = "RIPE"  # Ready for hearing
    UNRIPE_SUMMONS = "UNRIPE_SUMMONS"  # Waiting for summons service
    UNRIPE_DEPENDENT = "UNRIPE_DEPENDENT"  # Waiting for dependent case/order
    UNRIPE_PARTY = "UNRIPE_PARTY"  # Party/lawyer unavailable
    UNRIPE_DOCUMENT = "UNRIPE_DOCUMENT"  # Missing documents/evidence
    UNKNOWN = "UNKNOWN"  # Cannot determine

    def is_ripe(self) -> bool:
        """Check if status indicates ripeness."""
        return self == RipenessStatus.RIPE

    def is_unripe(self) -> bool:
        """Check if status indicates unripeness."""
        return self in {
            RipenessStatus.UNRIPE_SUMMONS,
            RipenessStatus.UNRIPE_DEPENDENT,
            RipenessStatus.UNRIPE_PARTY,
            RipenessStatus.UNRIPE_DOCUMENT,
        }


# Keywords indicating bottlenecks (data-driven from analyze_ripeness_patterns.py)
UNRIPE_KEYWORDS = {
    "SUMMONS": RipenessStatus.UNRIPE_SUMMONS,
    "NOTICE": RipenessStatus.UNRIPE_SUMMONS,
    "ISSUE": RipenessStatus.UNRIPE_SUMMONS,
    "SERVICE": RipenessStatus.UNRIPE_SUMMONS,
    "STAY": RipenessStatus.UNRIPE_DEPENDENT,
    "PENDING": RipenessStatus.UNRIPE_DEPENDENT,
}

RIPE_KEYWORDS = ["ARGUMENTS", "HEARING", "FINAL", "JUDGMENT", "ORDERS", "DISPOSAL"]


class RipenessClassifier:
    """Classify cases as RIPE or UNRIPE for scheduling optimization.

    Thresholds can be adjusted dynamically based on accuracy feedback.
    """

    # Stages that indicate case is ready for substantive hearing
    RIPE_STAGES = [
        "ARGUMENTS",
        "EVIDENCE",
        "ORDERS / JUDGMENT",
        "FINAL DISPOSAL"
    ]

    # Stages that indicate administrative/preliminary work
    UNRIPE_STAGES = [
        "PRE-ADMISSION",
        "ADMISSION",  # Most cases stuck here waiting for compliance
        "FRAMING OF CHARGES",
        "INTERLOCUTORY APPLICATION"
    ]

    # Minimum evidence thresholds before declaring a case RIPE
    # These can be adjusted via set_thresholds() for calibration
    MIN_SERVICE_HEARINGS = 1  # At least one hearing to confirm service/compliance
    MIN_STAGE_DAYS = 7  # Time spent in current stage to show compliance efforts
    MIN_CASE_AGE_DAYS = 14  # Minimum maturity before assuming readiness

    @classmethod
    def _has_required_evidence(cls, case: Case) -> tuple[bool, dict[str, bool]]:
        """Check that minimum readiness evidence exists before declaring RIPE."""
        # Evidence of service/compliance: at least one hearing or explicit purpose text
        service_confirmed = case.hearing_count >= cls.MIN_SERVICE_HEARINGS or bool(
            getattr(case, "last_hearing_purpose", None)
        )

        # Evidence the case has progressed in its current stage
        days_in_stage = getattr(case, "days_in_stage", 0)
        compliance_confirmed = (
            case.current_stage not in cls.UNRIPE_STAGES or days_in_stage >= cls.MIN_STAGE_DAYS
        )

        # Age-based maturity requirement
        age_confirmed = getattr(case, "age_days", 0) >= cls.MIN_CASE_AGE_DAYS

        evidence = {
            "service": service_confirmed,
            "compliance": compliance_confirmed,
            "age": age_confirmed,
        }

        return all(evidence.values()), evidence

    @classmethod
    def _has_ripe_signal(cls, case: Case) -> bool:
        """Check if stage or hearing purpose indicates readiness."""
        if case.current_stage in cls.RIPE_STAGES:
            return True

        if hasattr(case, "last_hearing_purpose") and case.last_hearing_purpose:
            purpose_upper = case.last_hearing_purpose.upper()
            return any(keyword in purpose_upper for keyword in RIPE_KEYWORDS)

        return False

    @classmethod
    def classify(cls, case: Case, current_date: datetime | None = None) -> RipenessStatus:
        """Classify case ripeness status with bottleneck type.

        Args:
            case: Case to classify
            current_date: Current simulation date (defaults to now)

        Returns:
            RipenessStatus enum indicating ripeness and bottleneck type

        Algorithm:
        1. Check last hearing purpose for explicit bottleneck keywords
        2. Check stage (ADMISSION vs ORDERS/JUDGMENT)
        3. Check case maturity (days since filing, hearing count)
        4. Check if stuck (many hearings but no progress)
        5. Require readiness evidence (service/compliance/age) else UNKNOWN
        6. Check explicit ripe signals (stage/purpose)
        7. Default to UNKNOWN if evidence exists but no ripe signal
        """
        if current_date is None:
            current_date = datetime.now()

        # 1. Check last hearing purpose for explicit bottleneck keywords
        if hasattr(case, "last_hearing_purpose") and case.last_hearing_purpose:
            purpose_upper = case.last_hearing_purpose.upper()

            for keyword, bottleneck_type in UNRIPE_KEYWORDS.items():
                if keyword in purpose_upper:
                    return bottleneck_type

        # 2. Check stage - ADMISSION stage with few hearings is likely unripe
        if case.current_stage == "ADMISSION":
            # New cases in ADMISSION (< 3 hearings) are often unripe
            if case.hearing_count < 3:
                return RipenessStatus.UNRIPE_SUMMONS

        # 3. Check if case is "stuck" (many hearings but no progress)
        if case.hearing_count > 10:
            # Calculate average days between hearings
            if case.age_days > 0:
                avg_gap = case.age_days / case.hearing_count

                # If average gap > 60 days, likely stuck due to bottleneck
                if avg_gap > 60:
                    return RipenessStatus.UNRIPE_PARTY

        # 4. Require explicit readiness evidence before declaring RIPE
        evidence_ok, _ = cls._has_required_evidence(case)
        if not evidence_ok:
            return RipenessStatus.UNKNOWN

        # 5. Check stage-based ripeness (ripe stages are substantive) or explicit RIPE signal
        if cls._has_ripe_signal(case):
            return RipenessStatus.RIPE

        # 6. Default to UNKNOWN if no bottlenecks but also no clear ripe signal
        return RipenessStatus.UNKNOWN

    @classmethod
    def get_ripeness_priority(cls, case: Case, current_date: datetime | None = None) -> float:
        """Get priority adjustment based on ripeness.

        Ripe cases should get judicial time priority over unripe cases
        when scheduling is tight.

        Returns:
            Priority multiplier (1.5 for RIPE, 0.7 for UNRIPE)
        """
        ripeness = cls.classify(case, current_date)
        return 1.5 if ripeness.is_ripe() else 0.7

    @classmethod
    def is_schedulable(cls, case: Case, current_date: datetime | None = None) -> bool:
        """Determine if a case can be scheduled for a hearing.

        A case is schedulable if:
        - It is RIPE (no bottlenecks)
        - It has been sufficient time since last hearing
        - It is not disposed

        Args:
            case: The case to check
            current_date: Current simulation date

        Returns:
            True if case can be scheduled, False otherwise
        """
        # Check disposal status
        if case.is_disposed:
            return False

        # Calculate current ripeness
        ripeness = cls.classify(case, current_date)

        # Only RIPE cases can be scheduled
        return ripeness.is_ripe()

    @classmethod
    def get_ripeness_reason(cls, ripeness_status: RipenessStatus) -> str:
        """Get human-readable explanation for ripeness status.

        Used in dashboard tooltips and reports.

        Args:
            ripeness_status: The status to explain

        Returns:
            Human-readable explanation string
        """
        reasons = {
            RipenessStatus.RIPE: "Case is ready for hearing (no bottlenecks detected)",
            RipenessStatus.UNRIPE_SUMMONS: "Waiting for summons service or notice response",
            RipenessStatus.UNRIPE_DEPENDENT: "Waiting for another case or court order",
            RipenessStatus.UNRIPE_PARTY: "Party or lawyer unavailable",
            RipenessStatus.UNRIPE_DOCUMENT: "Missing documents or evidence",
            RipenessStatus.UNKNOWN: "Insufficient readiness evidence; route to manual triage",
        }
        return reasons.get(ripeness_status, "Unknown status")

    @classmethod
    def estimate_ripening_time(cls, case: Case, current_date: datetime) -> timedelta | None:
        """Estimate time until case becomes ripe.

        This is a heuristic based on bottleneck type and historical data.

        Args:
            case: The case to evaluate
            current_date: Current simulation date

        Returns:
            Estimated timedelta until ripe, or None if already ripe or unknown
        """
        ripeness = cls.classify(case, current_date)

        if ripeness.is_ripe():
            return timedelta(0)

        # Heuristic estimates based on bottleneck type
        estimates = {
            RipenessStatus.UNRIPE_SUMMONS: timedelta(days=30),
            RipenessStatus.UNRIPE_DEPENDENT: timedelta(days=60),
            RipenessStatus.UNRIPE_PARTY: timedelta(days=14),
            RipenessStatus.UNRIPE_DOCUMENT: timedelta(days=21),
        }

        return estimates.get(ripeness, None)

    @classmethod
    def set_thresholds(cls, new_thresholds: dict[str, int | float]) -> None:
        """Update classification thresholds for calibration.

        Args:
            new_thresholds: Dictionary with threshold names and values
                           e.g., {"MIN_SERVICE_HEARINGS": 2, "MIN_STAGE_DAYS": 5}
        """
        for threshold_name, value in new_thresholds.items():
            if hasattr(cls, threshold_name):
                setattr(cls, threshold_name, int(value))
            else:
                raise ValueError(f"Unknown threshold: {threshold_name}")

    @classmethod
    def get_current_thresholds(cls) -> dict[str, int]:
        """Get current threshold values.

        Returns:
            Dictionary of threshold names and values
        """
        return {
            "MIN_SERVICE_HEARINGS": cls.MIN_SERVICE_HEARINGS,
            "MIN_STAGE_DAYS": cls.MIN_STAGE_DAYS,
            "MIN_CASE_AGE_DAYS": cls.MIN_CASE_AGE_DAYS,
        }
