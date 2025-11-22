"""Hearing event entity and outcome tracking.

This module defines the Hearing class which represents a scheduled court hearing
with its outcome and associated metadata.
"""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional


class HearingOutcome(Enum):
    """Possible outcomes of a hearing."""
    SCHEDULED = "SCHEDULED"       # Future hearing
    HEARD = "HEARD"               # Completed successfully
    ADJOURNED = "ADJOURNED"       # Postponed
    DISPOSED = "DISPOSED"         # Case concluded
    NO_SHOW = "NO_SHOW"           # Party absent
    WITHDRAWN = "WITHDRAWN"       # Case withdrawn


@dataclass
class Hearing:
    """Represents a scheduled court hearing event.
    
    Attributes:
        hearing_id: Unique identifier
        case_id: Associated case
        scheduled_date: Date of hearing
        courtroom_id: Assigned courtroom
        judge_id: Presiding judge
        stage: Case stage at time of hearing
        outcome: Result of hearing
        actual_date: Actual date if rescheduled
        duration_minutes: Estimated duration
        notes: Optional notes
    """
    hearing_id: str
    case_id: str
    scheduled_date: date
    courtroom_id: int
    judge_id: str
    stage: str
    outcome: HearingOutcome = HearingOutcome.SCHEDULED
    actual_date: Optional[date] = None
    duration_minutes: int = 30
    notes: Optional[str] = None
    
    def mark_as_heard(self, actual_date: Optional[date] = None) -> None:
        """Mark hearing as successfully completed.
        
        Args:
            actual_date: Actual date if different from scheduled
        """
        self.outcome = HearingOutcome.HEARD
        self.actual_date = actual_date or self.scheduled_date
    
    def mark_as_adjourned(self, reason: str = "") -> None:
        """Mark hearing as adjourned.
        
        Args:
            reason: Reason for adjournment
        """
        self.outcome = HearingOutcome.ADJOURNED
        if reason:
            self.notes = reason
    
    def mark_as_disposed(self) -> None:
        """Mark hearing as final disposition."""
        self.outcome = HearingOutcome.DISPOSED
        self.actual_date = self.scheduled_date
    
    def mark_as_no_show(self, party: str = "") -> None:
        """Mark hearing as no-show.
        
        Args:
            party: Which party was absent
        """
        self.outcome = HearingOutcome.NO_SHOW
        if party:
            self.notes = f"No show: {party}"
    
    def reschedule(self, new_date: date) -> None:
        """Reschedule hearing to a new date.
        
        Args:
            new_date: New scheduled date
        """
        self.scheduled_date = new_date
        self.outcome = HearingOutcome.SCHEDULED
    
    def is_complete(self) -> bool:
        """Check if hearing has concluded.
        
        Returns:
            True if outcome is not SCHEDULED
        """
        return self.outcome != HearingOutcome.SCHEDULED
    
    def is_successful(self) -> bool:
        """Check if hearing was successfully held.
        
        Returns:
            True if outcome is HEARD or DISPOSED
        """
        return self.outcome in (HearingOutcome.HEARD, HearingOutcome.DISPOSED)
    
    def get_effective_date(self) -> date:
        """Get actual or scheduled date.
        
        Returns:
            actual_date if set, else scheduled_date
        """
        return self.actual_date or self.scheduled_date
    
    def __repr__(self) -> str:
        return (f"Hearing(id={self.hearing_id}, case={self.case_id}, "
                f"date={self.scheduled_date}, outcome={self.outcome.value})")
    
    def to_dict(self) -> dict:
        """Convert hearing to dictionary for serialization."""
        return {
            "hearing_id": self.hearing_id,
            "case_id": self.case_id,
            "scheduled_date": self.scheduled_date.isoformat(),
            "actual_date": self.actual_date.isoformat() if self.actual_date else None,
            "courtroom_id": self.courtroom_id,
            "judge_id": self.judge_id,
            "stage": self.stage,
            "outcome": self.outcome.value,
            "duration_minutes": self.duration_minutes,
            "notes": self.notes,
        }
