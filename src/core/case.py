"""Case entity and lifecycle management.

This module defines the Case class which represents a single court case
progressing through various stages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from src.data.config import TERMINAL_STAGES

if TYPE_CHECKING:
    from src.core.ripeness import RipenessStatus
else:
    # Import at runtime
    RipenessStatus = None


class CaseStatus(Enum):
    """Status of a case in the system."""

    PENDING = "pending"  # Filed, awaiting first hearing
    ACTIVE = "active"  # Has had at least one hearing
    ADJOURNED = "adjourned"  # Last hearing was adjourned
    DISPOSED = "disposed"  # Final disposal/settlement reached


@dataclass
class Case:
    """Represents a single court case.

    Attributes:
        case_id: Unique identifier (like CNR number)
        case_type: Type of case (RSA, CRP, RFA, CA, CCC, CP, CMP)
        filed_date: Date when case was filed
        current_stage: Current stage in lifecycle
        status: Current status (PENDING, ACTIVE, ADJOURNED, DISPOSED)
        courtroom_id: Assigned courtroom (0-4 for 5 courtrooms)
        is_urgent: Whether case is marked urgent
        readiness_score: Computed readiness score (0-1)
        hearing_count: Number of hearings held
        last_hearing_date: Date of most recent hearing
        days_since_last_hearing: Days elapsed since last hearing
        age_days: Days since filing
        disposal_date: Date of disposal (if disposed)
        history: List of hearing dates and outcomes
    """

    case_id: str
    case_type: str
    filed_date: date
    current_stage: str = "ADMISSION"  # Default initial stage
    status: CaseStatus = CaseStatus.PENDING
    courtroom_id: int | None = None  # None = not yet assigned; 0 is invalid
    is_urgent: bool = False
    readiness_score: float = 0.0
    hearing_count: int = 0
    last_hearing_date: Optional[date] = None
    days_since_last_hearing: int = 0
    age_days: int = 0
    disposal_date: Optional[date] = None
    stage_start_date: Optional[date] = None
    days_in_stage: int = 0
    history: List[dict] = field(default_factory=list)

    # Ripeness tracking (NEW - for bottleneck detection)
    ripeness_status: str = "UNKNOWN"  # RipenessStatus enum value (stored as string to avoid circular import)
    bottleneck_reason: Optional[str] = None
    ripeness_updated_at: Optional[datetime] = None
    last_hearing_purpose: Optional[str] = (
        None  # Purpose of last hearing (for classification)
    )

    # No-case-left-behind tracking (NEW)
    last_scheduled_date: Optional[date] = None
    days_since_last_scheduled: int = 0

    def progress_to_stage(self, new_stage: str, current_date: date) -> None:
        """Progress case to a new stage.

        Args:
            new_stage: The stage to progress to
            current_date: Current simulation date
        """
        self.current_stage = new_stage
        self.stage_start_date = current_date
        self.days_in_stage = 0

        # Check if terminal stage (case disposed)
        if new_stage in TERMINAL_STAGES:
            self.status = CaseStatus.DISPOSED
            self.disposal_date = current_date

        # Record in history
        self.history.append(
            {
                "date": current_date,
                "event": "stage_change",
                "stage": new_stage,
            }
        )

    def record_hearing(
        self, hearing_date: date, was_heard: bool, outcome: str = ""
    ) -> None:
        """Record a hearing event.

        Args:
            hearing_date: Date of the hearing
            was_heard: Whether the hearing actually proceeded (not adjourned)
            outcome: Outcome description
        """
        self.hearing_count += 1
        self.last_hearing_date = hearing_date

        if was_heard:
            self.status = CaseStatus.ACTIVE
        else:
            self.status = CaseStatus.ADJOURNED

        # Record in history
        self.history.append(
            {
                "date": hearing_date,
                "event": "hearing",
                "was_heard": was_heard,
                "outcome": outcome,
                "stage": self.current_stage,
            }
        )

    def update_age(self, current_date: date) -> None:
        """Update age and days since last hearing.

        Args:
            current_date: Current simulation date
        """
        self.age_days = (current_date - self.filed_date).days

        if self.last_hearing_date:
            self.days_since_last_hearing = (current_date - self.last_hearing_date).days
        else:
            self.days_since_last_hearing = self.age_days

        if self.stage_start_date:
            self.days_in_stage = (current_date - self.stage_start_date).days
        else:
            self.days_in_stage = self.age_days

        # Update days since last scheduled (for no-case-left-behind tracking)
        if self.last_scheduled_date:
            self.days_since_last_scheduled = (
                current_date - self.last_scheduled_date
            ).days
        else:
            self.days_since_last_scheduled = self.age_days

    def compute_readiness_score(self) -> float:
        """Compute readiness score based on hearings, gaps, and stage.

        Formula (from EDA):
            READINESS = (hearings_capped/50) * 0.4 +
                       (100/gap_clamped) * 0.3 +
                       (stage_advanced) * 0.3

        Returns:
            Readiness score (0-1, higher = more ready)
        """
        # Cap hearings at 50
        hearings_capped = min(self.hearing_count, 50)
        hearings_component = (hearings_capped / 50) * 0.4

        # Gap component (inverse of days since last hearing)
        gap_clamped = min(max(self.days_since_last_hearing, 1), 100)
        gap_component = (100 / gap_clamped) * 0.3

        # Stage component (advanced stages get higher score)
        advanced_stages = ["ARGUMENTS", "EVIDENCE", "ORDERS / JUDGMENT"]
        stage_component = 0.3 if self.current_stage in advanced_stages else 0.1

        readiness = hearings_component + gap_component + stage_component
        self.readiness_score = min(1.0, max(0.0, readiness))

        return self.readiness_score

    def is_ready_for_scheduling(self, min_gap_days: int = 7) -> bool:
        """Check if case is ready to be scheduled.

        Args:
            min_gap_days: Minimum days required since last hearing

        Returns:
            True if case can be scheduled
        """
        if self.status == CaseStatus.DISPOSED:
            return False

        if self.last_hearing_date is None:
            return True  # First hearing, always ready

        return self.days_since_last_hearing >= min_gap_days

    def needs_alert(self, max_gap_days: int = 90) -> bool:
        """Check if case needs alert due to long gap.

        Args:
            max_gap_days: Maximum allowed gap before alert

        Returns:
            True if alert should be triggered
        """
        if self.status == CaseStatus.DISPOSED:
            return False

        return self.days_since_last_hearing > max_gap_days

    def get_priority_score(self) -> float:
        """Get overall priority score for scheduling.

        Combines age, readiness, urgency, and adjournment boost into single score.

        Formula:
            priority = age*0.35 + readiness*0.25 + urgency*0.25 + adjournment_boost*0.15

        Adjournment boost: Recently adjourned cases get priority to avoid indefinite postponement.
        The boost decays exponentially: strongest immediately after adjournment, weaker over time.

        Returns:
            Priority score (higher = higher priority)
        """
        # Age component (normalize to 0-1, assuming max age ~2000 days)
        age_component = min(self.age_days / 2000, 1.0) * 0.35

        # Readiness component
        readiness_component = self.readiness_score * 0.25

        # Urgency component
        urgency_component = 1.0 if self.is_urgent else 0.0
        urgency_component *= 0.25

        # Adjournment boost (NEW - prevents cases from being repeatedly postponed)
        adjournment_boost = 0.0
        if self.status == CaseStatus.ADJOURNED and self.hearing_count > 0:
            # Boost starts at 1.0 immediately after adjournment, decays exponentially
            # Formula: boost = exp(-days_since_hearing / 21)
            # At 7 days: ~0.71 (strong boost)
            # At 14 days: ~0.50 (moderate boost)
            # At 21 days: ~0.37 (weak boost)
            # At 28 days: ~0.26 (very weak boost)
            import math

            decay_factor = 21  # Half-life of boost
            adjournment_boost = math.exp(-self.days_since_last_hearing / decay_factor)
        adjournment_boost *= 0.15

        return (
            age_component + readiness_component + urgency_component + adjournment_boost
        )

    def mark_unripe(self, status, reason: str, current_date: datetime) -> None:
        """Mark case as unripe with bottleneck reason.

        Args:
            status: Ripeness status (UNRIPE_SUMMONS, UNRIPE_PARTY, etc.) - RipenessStatus enum
            reason: Human-readable reason for unripeness
            current_date: Current simulation date
        """
        # Store as string to avoid circular import
        self.ripeness_status = status.value if hasattr(status, "value") else str(status)
        self.bottleneck_reason = reason
        self.ripeness_updated_at = current_date

        # Record in history
        self.history.append(
            {
                "date": current_date,
                "event": "ripeness_change",
                "status": self.ripeness_status,
                "reason": reason,
            }
        )

    def mark_ripe(self, current_date: datetime) -> None:
        """Mark case as ripe (ready for hearing).

        Args:
            current_date: Current simulation date
        """
        self.ripeness_status = "RIPE"
        self.bottleneck_reason = None
        self.ripeness_updated_at = current_date

        # Record in history
        self.history.append(
            {
                "date": current_date,
                "event": "ripeness_change",
                "status": "RIPE",
                "reason": "Case became ripe",
            }
        )

    def mark_scheduled(self, scheduled_date: date) -> None:
        """Mark case as scheduled for a hearing.

        Used for no-case-left-behind tracking.

        Args:
            scheduled_date: Date case was scheduled
        """
        self.last_scheduled_date = scheduled_date
        self.days_since_last_scheduled = 0

    @property
    def is_disposed(self) -> bool:
        """Check if case is disposed."""
        return self.status == CaseStatus.DISPOSED

    def __repr__(self) -> str:
        return (
            f"Case(id={self.case_id}, type={self.case_type}, "
            f"stage={self.current_stage}, status={self.status.value}, "
            f"hearings={self.hearing_count})"
        )

    def to_dict(self) -> dict:
        """Convert case to dictionary for serialization."""
        return {
            "case_id": self.case_id,
            "case_type": self.case_type,
            "filed_date": self.filed_date.isoformat(),
            "current_stage": self.current_stage,
            "status": self.status.value,
            "courtroom_id": self.courtroom_id,
            "is_urgent": self.is_urgent,
            "readiness_score": self.readiness_score,
            "hearing_count": self.hearing_count,
            "last_hearing_date": self.last_hearing_date.isoformat()
            if self.last_hearing_date
            else None,
            "days_since_last_hearing": self.days_since_last_hearing,
            "age_days": self.age_days,
            "disposal_date": self.disposal_date.isoformat()
            if self.disposal_date
            else None,
            "ripeness_status": self.ripeness_status,
            "bottleneck_reason": self.bottleneck_reason,
            "last_hearing_purpose": self.last_hearing_purpose,
            "last_scheduled_date": self.last_scheduled_date.isoformat()
            if self.last_scheduled_date
            else None,
            "days_since_last_scheduled": self.days_since_last_scheduled,
            "history": self.history,
        }
