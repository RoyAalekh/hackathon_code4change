"""Shared reward helper utilities for RL agents.

The helper operates on episode-level statistics so that reward shaping
reflects system-wide outcomes (disposal rate, gap compliance, urgent
case latency, and fairness across cases).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Iterable, Optional

import numpy as np

from scheduler.core.case import Case


@dataclass
class EpisodeRewardHelper:
    """Aggregates episode metrics and computes shaped rewards."""

    total_cases: int
    target_gap_days: int = 30
    max_urgent_latency: int = 60
    disposal_weight: float = 4.0
    gap_weight: float = 1.5
    urgent_weight: float = 2.0
    fairness_weight: float = 1.0
    _disposed_cases: int = 0
    _hearing_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    _urgent_latencies: list[float] = field(default_factory=list)

    def _base_outcome_reward(self, case: Case, was_scheduled: bool, hearing_outcome: str) -> float:
        """Preserve the original per-case shaping signals."""

        reward = 0.0
        if not was_scheduled:
            return reward

        # Base scheduling reward (small positive for taking action)
        reward += 0.5

        # Hearing outcome rewards
        lower_outcome = hearing_outcome.lower()
        if "disposal" in lower_outcome or "judgment" in lower_outcome or "settlement" in lower_outcome:
            reward += 10.0  # Major positive for disposal
        elif "progress" in lower_outcome and "adjourn" not in lower_outcome:
            reward += 3.0  # Progress without disposal
        elif "adjourn" in lower_outcome:
            reward -= 3.0  # Negative for adjournment

        # Urgency bonus
        if case.is_urgent:
            reward += 2.0

        # Ripeness penalty
        if hasattr(case, "ripeness_status") and case.ripeness_status not in ["RIPE", "UNKNOWN"]:
            reward -= 4.0

        # Long pending bonus (>365 days)
        if case.age_days and case.age_days > 365:
            reward += 2.0

        return reward

    def _fairness_score(self) -> float:
        """Reward higher uniformity in hearing distribution."""

        counts: Iterable[int] = self._hearing_counts.values()
        if not counts:
            return 0.0

        counts_array = np.array(list(counts), dtype=float)
        mean = np.mean(counts_array)
        if mean == 0:
            return 0.0

        dispersion = np.std(counts_array) / (mean + 1e-6)
        # Lower dispersion -> better fairness. Convert to reward in [0, 1].
        fairness = max(0.0, 1.0 - dispersion)
        return fairness

    def compute_case_reward(
        self,
        case: Case,
        was_scheduled: bool,
        hearing_outcome: str,
        current_date,
        previous_gap_days: Optional[int] = None,
    ) -> float:
        """Compute reward using both local and episode-level signals."""

        reward = self._base_outcome_reward(case, was_scheduled, hearing_outcome)

        if not was_scheduled:
            return reward

        # Track disposals
        if "disposal" in hearing_outcome.lower() or getattr(case, "is_disposed", False):
            self._disposed_cases += 1

        # Track hearing counts for fairness
        self._hearing_counts[case.case_id] = case.hearing_count or self._hearing_counts[case.case_id] + 1

        # Track urgent latencies
        if case.is_urgent:
            self._urgent_latencies.append(case.age_days or 0)

        # Episode-level components
        disposal_rate = (self._disposed_cases / self.total_cases) if self.total_cases else 0.0
        reward += self.disposal_weight * disposal_rate

        if previous_gap_days is not None:
            gap_score = max(0.0, 1.0 - (previous_gap_days / self.target_gap_days))
            reward += self.gap_weight * gap_score

        if self._urgent_latencies:
            avg_latency = float(np.mean(self._urgent_latencies))
            latency_score = max(0.0, 1.0 - (avg_latency / self.max_urgent_latency))
            reward += self.urgent_weight * latency_score

        fairness = self._fairness_score()
        reward += self.fairness_weight * fairness

        return reward

