"""Age-based scheduling policy.

Prioritizes older cases to reduce maximum age and prevent starvation.
Uses case age (days since filing) as primary criterion.
"""
from __future__ import annotations

from datetime import date
from typing import List

from scheduler.core.policy import SchedulerPolicy
from scheduler.core.case import Case


class AgeBasedPolicy(SchedulerPolicy):
    """Age-based scheduling: oldest cases scheduled first."""
    
    def prioritize(self, cases: List[Case], current_date: date) -> List[Case]:
        """Sort cases by age (oldest first).
        
        Args:
            cases: List of eligible cases
            current_date: Current simulation date
            
        Returns:
            Cases sorted by age_days (descending)
        """
        # Update ages first
        for c in cases:
            c.update_age(current_date)
        
        return sorted(cases, key=lambda c: c.age_days, reverse=True)
    
    def get_name(self) -> str:
        return "Age-Based"
    
    def requires_readiness_score(self) -> bool:
        return False
