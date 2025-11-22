"""Base scheduler interface for policy implementations.

This module defines the abstract interface that all scheduling policies must implement.
Each policy decides which cases to schedule on a given day based on different criteria.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import List

from scheduler.core.case import Case


class SchedulerPolicy(ABC):
    """Abstract base class for scheduling policies.
    
    All scheduling policies must implement the `prioritize` method which
    ranks cases for scheduling on a given day.
    """
    
    @abstractmethod
    def prioritize(self, cases: List[Case], current_date: date) -> List[Case]:
        """Prioritize cases for scheduling on the given date.
        
        Args:
            cases: List of eligible cases (already filtered for readiness, not disposed)
            current_date: Current simulation date
            
        Returns:
            Sorted list of cases in priority order (highest priority first)
        """
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Get the policy name for logging/reporting."""
        pass
    
    @abstractmethod
    def requires_readiness_score(self) -> bool:
        """Return True if this policy requires readiness score computation."""
        pass
