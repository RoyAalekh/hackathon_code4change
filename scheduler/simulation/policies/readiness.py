"""Readiness-based scheduling policy.

Combines age, readiness score, and urgency into a composite priority score.
This is the most sophisticated policy, balancing fairness with efficiency.

Priority formula:
  priority = (age/2000) * 0.4 + readiness * 0.3 + urgent * 0.3
"""
from __future__ import annotations

from datetime import date
from typing import List

from scheduler.core.case import Case
from scheduler.core.policy import SchedulerPolicy


class ReadinessPolicy(SchedulerPolicy):
    """Readiness-based scheduling: composite priority score."""

    def prioritize(self, cases: List[Case], current_date: date) -> List[Case]:
        """Sort cases by composite priority score (highest first).

        The priority score combines:
        - Age (40% weight)
        - Readiness (30% weight)
        - Urgency (30% weight)

        Args:
            cases: List of eligible cases
            current_date: Current simulation date

        Returns:
            Cases sorted by priority score (descending)
        """
        # Update ages and compute readiness
        for c in cases:
            c.update_age(current_date)
            c.compute_readiness_score()

        # Sort by priority score (higher = more urgent)
        return sorted(cases, key=lambda c: c.get_priority_score(), reverse=True)

    def get_name(self) -> str:
        return "Readiness-Based"

    def requires_readiness_score(self) -> bool:
        return True
