"""First-In-First-Out (FIFO) scheduling policy.

Schedules cases in the order they were filed, treating all cases equally.
This is the simplest baseline policy.
"""
from __future__ import annotations

from datetime import date
from typing import List

from scheduler.core.policy import SchedulerPolicy
from scheduler.core.case import Case


class FIFOPolicy(SchedulerPolicy):
    """FIFO scheduling: cases scheduled in filing order."""
    
    def prioritize(self, cases: List[Case], current_date: date) -> List[Case]:
        """Sort cases by filed_date (earliest first).
        
        Args:
            cases: List of eligible cases
            current_date: Current simulation date (unused)
            
        Returns:
            Cases sorted by filing date (oldest first)
        """
        return sorted(cases, key=lambda c: c.filed_date)
    
    def get_name(self) -> str:
        return "FIFO"
    
    def requires_readiness_score(self) -> bool:
        return False
