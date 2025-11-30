"""Courtroom resource management.

This module defines the Courtroom class which represents a physical courtroom
with capacity constraints and daily scheduling.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Set

from scheduler.data.config import DEFAULT_DAILY_CAPACITY


@dataclass
class Courtroom:
    """Represents a courtroom resource.

    Attributes:
        courtroom_id: Unique identifier (0-4 for 5 courtrooms)
        judge_id: Currently assigned judge (optional)
        daily_capacity: Maximum cases that can be heard per day
        case_types: Types of cases handled by this courtroom
        schedule: Dict mapping dates to lists of case_ids scheduled
        hearings_held: Count of hearings held
        utilization_history: Track daily utilization rates
    """
    courtroom_id: int
    judge_id: Optional[str] = None
    daily_capacity: int = DEFAULT_DAILY_CAPACITY
    case_types: Set[str] = field(default_factory=set)
    schedule: Dict[date, List[str]] = field(default_factory=dict)
    hearings_held: int = 0
    utilization_history: List[Dict] = field(default_factory=list)

    def assign_judge(self, judge_id: str) -> None:
        """Assign a judge to this courtroom.

        Args:
            judge_id: Judge identifier
        """
        self.judge_id = judge_id

    def add_case_types(self, *case_types: str) -> None:
        """Add case types that this courtroom handles.

        Args:
            *case_types: One or more case type strings (e.g., 'RSA', 'CRP')
        """
        self.case_types.update(case_types)

    def can_schedule(self, hearing_date: date, case_id: str) -> bool:
        """Check if a case can be scheduled on a given date.

        Args:
            hearing_date: Date to check
            case_id: Case identifier

        Returns:
            True if slot available, False if at capacity
        """
        if hearing_date not in self.schedule:
            return True  # No hearings scheduled yet

        # Check if already scheduled
        if case_id in self.schedule[hearing_date]:
            return False  # Already scheduled

        # Check capacity
        return len(self.schedule[hearing_date]) < self.daily_capacity

    def schedule_case(self, hearing_date: date, case_id: str) -> bool:
        """Schedule a case for a hearing.

        Args:
            hearing_date: Date of hearing
            case_id: Case identifier

        Returns:
            True if successfully scheduled, False if at capacity
        """
        if not self.can_schedule(hearing_date, case_id):
            return False

        if hearing_date not in self.schedule:
            self.schedule[hearing_date] = []

        self.schedule[hearing_date].append(case_id)
        return True

    def unschedule_case(self, hearing_date: date, case_id: str) -> bool:
        """Remove a case from schedule (e.g., if adjourned).

        Args:
            hearing_date: Date of hearing
            case_id: Case identifier

        Returns:
            True if successfully removed, False if not found
        """
        if hearing_date not in self.schedule:
            return False

        if case_id in self.schedule[hearing_date]:
            self.schedule[hearing_date].remove(case_id)
            return True

        return False

    def get_daily_schedule(self, hearing_date: date) -> List[str]:
        """Get list of cases scheduled for a specific date.

        Args:
            hearing_date: Date to query

        Returns:
            List of case_ids scheduled (empty if none)
        """
        return self.schedule.get(hearing_date, [])

    def get_capacity_for_date(self, hearing_date: date) -> int:
        """Get remaining capacity for a specific date.

        Args:
            hearing_date: Date to query

        Returns:
            Number of available slots
        """
        scheduled_count = len(self.get_daily_schedule(hearing_date))
        return self.daily_capacity - scheduled_count

    def record_hearing_completed(self, hearing_date: date) -> None:
        """Record that a hearing was held.

        Args:
            hearing_date: Date of hearing
        """
        self.hearings_held += 1

    def compute_utilization(self, hearing_date: date) -> float:
        """Compute utilization rate for a specific date.

        Args:
            hearing_date: Date to compute for

        Returns:
            Utilization rate (0.0 to 1.0)
        """
        scheduled_count = len(self.get_daily_schedule(hearing_date))
        return scheduled_count / self.daily_capacity if self.daily_capacity > 0 else 0.0

    def record_daily_utilization(self, hearing_date: date, actual_hearings: int) -> None:
        """Record actual utilization for a day.

        Args:
            hearing_date: Date of hearings
            actual_hearings: Number of hearings actually held (not adjourned)
        """
        scheduled = len(self.get_daily_schedule(hearing_date))
        utilization = actual_hearings / self.daily_capacity if self.daily_capacity > 0 else 0.0

        self.utilization_history.append({
            "date": hearing_date,
            "scheduled": scheduled,
            "actual": actual_hearings,
            "capacity": self.daily_capacity,
            "utilization": utilization,
        })

    def get_average_utilization(self) -> float:
        """Calculate average utilization rate across all recorded days.

        Returns:
            Average utilization (0.0 to 1.0)
        """
        if not self.utilization_history:
            return 0.0

        total = sum(day["utilization"] for day in self.utilization_history)
        return total / len(self.utilization_history)

    def get_schedule_summary(self, start_date: date, end_date: date) -> Dict:
        """Get summary statistics for a date range.

        Args:
            start_date: Start of range
            end_date: End of range

        Returns:
            Dict with counts and utilization stats
        """
        days_in_range = [d for d in self.schedule.keys()
                        if start_date <= d <= end_date]

        total_scheduled = sum(len(self.schedule[d]) for d in days_in_range)
        days_with_hearings = len(days_in_range)

        return {
            "courtroom_id": self.courtroom_id,
            "days_with_hearings": days_with_hearings,
            "total_cases_scheduled": total_scheduled,
            "avg_cases_per_day": total_scheduled / days_with_hearings if days_with_hearings > 0 else 0,
            "total_capacity": days_with_hearings * self.daily_capacity,
            "utilization_rate": total_scheduled / (days_with_hearings * self.daily_capacity)
                              if days_with_hearings > 0 else 0,
        }

    def clear_schedule(self) -> None:
        """Clear all scheduled hearings (for testing/reset)."""
        self.schedule.clear()
        self.utilization_history.clear()
        self.hearings_held = 0

    def __repr__(self) -> str:
        return (f"Courtroom(id={self.courtroom_id}, judge={self.judge_id}, "
                f"capacity={self.daily_capacity}, types={self.case_types})")

    def to_dict(self) -> dict:
        """Convert courtroom to dictionary for serialization."""
        return {
            "courtroom_id": self.courtroom_id,
            "judge_id": self.judge_id,
            "daily_capacity": self.daily_capacity,
            "case_types": list(self.case_types),
            "schedule_size": len(self.schedule),
            "hearings_held": self.hearings_held,
            "avg_utilization": self.get_average_utilization(),
        }
