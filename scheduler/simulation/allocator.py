"""
Dynamic courtroom allocation system.

Allocates cases across multiple courtrooms using configurable strategies:
- LOAD_BALANCED: Distributes cases evenly across courtrooms
- TYPE_AFFINITY: Prefers courtrooms with history of similar case types (future)
- CONTINUITY: Keeps cases in same courtroom when possible (future)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scheduler.core.case import Case


class AllocationStrategy(Enum):
    """Strategies for allocating cases to courtrooms."""

    LOAD_BALANCED = "load_balanced"  # Minimize load variance across courtrooms
    TYPE_AFFINITY = "type_affinity"  # Group similar case types in same courtroom
    CONTINUITY = "continuity"  # Keep cases in same courtroom across hearings


@dataclass
class CourtroomState:
    """Tracks state of a single courtroom."""

    courtroom_id: int
    daily_load: int = 0  # Number of cases scheduled today
    total_cases_handled: int = 0  # Lifetime count
    case_type_distribution: dict[str, int] = field(default_factory=dict)  # Type -> count

    def add_case(self, case: Case) -> None:
        """Register a case assigned to this courtroom."""
        self.daily_load += 1
        self.total_cases_handled += 1
        self.case_type_distribution[case.case_type] = (
            self.case_type_distribution.get(case.case_type, 0) + 1
        )

    def reset_daily_load(self) -> None:
        """Reset daily load counter at start of new day."""
        self.daily_load = 0

    def has_capacity(self, max_capacity: int) -> bool:
        """Check if courtroom can accept more cases today."""
        return self.daily_load < max_capacity


class CourtroomAllocator:
    """
    Dynamically allocates cases to courtrooms using load balancing.

    Ensures fair distribution of workload across courtrooms while respecting
    capacity constraints. Future versions may add judge specialization matching
    and case type affinity.
    """

    def __init__(
        self,
        num_courtrooms: int = 5,
        per_courtroom_capacity: int = 10,
        strategy: AllocationStrategy = AllocationStrategy.LOAD_BALANCED,
    ):
        """
        Initialize allocator.

        Args:
            num_courtrooms: Number of courtrooms to allocate across
            per_courtroom_capacity: Max cases per courtroom per day
            strategy: Allocation strategy to use
        """
        self.num_courtrooms = num_courtrooms
        self.per_courtroom_capacity = per_courtroom_capacity
        self.strategy = strategy

        # Initialize courtroom states
        self.courtrooms = {
            i: CourtroomState(courtroom_id=i) for i in range(1, num_courtrooms + 1)
        }

        # Metrics tracking
        self.daily_loads: dict[date, dict[int, int]] = {}  # date -> {courtroom_id -> load}
        self.allocation_changes: int = 0  # Cases that switched courtrooms
        self.capacity_rejections: int = 0  # Cases that couldn't be allocated

    def allocate(self, cases: list[Case], current_date: date) -> dict[str, int]:
        """
        Allocate cases to courtrooms for a given date.

        Args:
            cases: List of cases to allocate (already prioritized by caller)
            current_date: Date of allocation

        Returns:
            Mapping of case_id -> courtroom_id for allocated cases
        """
        # Reset daily loads for new day
        for courtroom in self.courtrooms.values():
            courtroom.reset_daily_load()

        allocations: dict[str, int] = {}

        for case in cases:
            # Find best courtroom based on strategy
            courtroom_id = self._find_best_courtroom(case)

            if courtroom_id is None:
                # No courtroom has capacity
                self.capacity_rejections += 1
                continue

            # Track if courtroom changed (only count actual switches, not initial assignments)
            if case.courtroom_id is not None and case.courtroom_id != 0 and case.courtroom_id != courtroom_id:
                self.allocation_changes += 1

            # Assign case to courtroom
            case.courtroom_id = courtroom_id
            self.courtrooms[courtroom_id].add_case(case)
            allocations[case.case_id] = courtroom_id

        # Record daily loads
        self.daily_loads[current_date] = {
            cid: court.daily_load for cid, court in self.courtrooms.items()
        }

        return allocations

    def _find_best_courtroom(self, case: Case) -> int | None:
        """
        Find best courtroom for a case based on allocation strategy.

        Args:
            case: Case to allocate

        Returns:
            Courtroom ID or None if all at capacity
        """
        if self.strategy == AllocationStrategy.LOAD_BALANCED:
            return self._find_least_loaded_courtroom()
        elif self.strategy == AllocationStrategy.TYPE_AFFINITY:
            return self._find_type_affinity_courtroom(case)
        elif self.strategy == AllocationStrategy.CONTINUITY:
            return self._find_continuity_courtroom(case)
        else:
            return self._find_least_loaded_courtroom()

    def _find_least_loaded_courtroom(self) -> int | None:
        """Find courtroom with lowest daily load that has capacity."""
        available = [
            (cid, court)
            for cid, court in self.courtrooms.items()
            if court.has_capacity(self.per_courtroom_capacity)
        ]

        if not available:
            return None

        # Return courtroom with minimum load
        return min(available, key=lambda x: x[1].daily_load)[0]

    def _find_type_affinity_courtroom(self, case: Case) -> int | None:
        """Find courtroom with most similar case type history (future enhancement)."""
        # For now, fall back to load balancing
        # Future: score courtrooms by case_type_distribution similarity
        return self._find_least_loaded_courtroom()

    def _find_continuity_courtroom(self, case: Case) -> int | None:
        """Try to keep case in same courtroom as previous hearing (future enhancement)."""
        # If case already has courtroom assignment and it has capacity, keep it there
        if case.courtroom_id is not None:
            courtroom = self.courtrooms.get(case.courtroom_id)
            if courtroom and courtroom.has_capacity(self.per_courtroom_capacity):
                return case.courtroom_id

        # Otherwise fall back to load balancing
        return self._find_least_loaded_courtroom()

    def get_utilization_stats(self) -> dict:
        """
        Calculate courtroom utilization statistics.

        Returns:
            Dictionary with utilization metrics
        """
        if not self.daily_loads:
            return {}

        # Flatten daily loads into list of loads per courtroom
        all_loads = [
            loads[cid]
            for loads in self.daily_loads.values()
            for cid in range(1, self.num_courtrooms + 1)
        ]

        # Calculate per-courtroom averages
        courtroom_totals = {cid: 0 for cid in range(1, self.num_courtrooms + 1)}
        for loads in self.daily_loads.values():
            for cid, load in loads.items():
                courtroom_totals[cid] += load

        num_days = len(self.daily_loads)
        courtroom_avgs = {cid: total / num_days for cid, total in courtroom_totals.items()}

        # Calculate Gini coefficient for fairness
        sorted_totals = sorted(courtroom_totals.values())
        n = len(sorted_totals)
        if n == 0 or sum(sorted_totals) == 0:
            gini = 0.0
        else:
            cumsum = 0
            for i, total in enumerate(sorted_totals):
                cumsum += (i + 1) * total
            gini = (2 * cumsum) / (n * sum(sorted_totals)) - (n + 1) / n

        return {
            "avg_daily_load": sum(all_loads) / len(all_loads) if all_loads else 0,
            "max_daily_load": max(all_loads) if all_loads else 0,
            "min_daily_load": min(all_loads) if all_loads else 0,
            "courtroom_averages": courtroom_avgs,
            "courtroom_totals": courtroom_totals,
            "load_balance_gini": gini,
            "allocation_changes": self.allocation_changes,
            "capacity_rejections": self.capacity_rejections,
            "total_days": num_days,
        }

    def get_courtroom_summary(self) -> str:
        """Generate human-readable summary of courtroom allocation."""
        stats = self.get_utilization_stats()

        if not stats:
            return "No allocations performed yet"

        lines = [
            "Courtroom Allocation Summary",
            "=" * 50,
            f"Strategy: {self.strategy.value}",
            f"Number of courtrooms: {self.num_courtrooms}",
            f"Per-courtroom capacity: {self.per_courtroom_capacity} cases/day",
            f"Total simulation days: {stats['total_days']}",
            "",
            "Load Distribution:",
            f"  Average daily load: {stats['avg_daily_load']:.1f} cases",
            f"  Max daily load: {stats['max_daily_load']} cases",
            f"  Min daily load: {stats['min_daily_load']} cases",
            f"  Load balance fairness (Gini): {stats['load_balance_gini']:.3f}",
            "",
            "Courtroom-wise totals:",
        ]

        for cid in range(1, self.num_courtrooms + 1):
            total = stats["courtroom_totals"][cid]
            avg = stats["courtroom_averages"][cid]
            lines.append(f"  Courtroom {cid}: {total:,} cases ({avg:.1f}/day)")

        lines.extend(
            [
                "",
                "Allocation behavior:",
                f"  Cases switched courtrooms: {stats['allocation_changes']:,}",
                f"  Capacity rejections: {stats['capacity_rejections']:,}",
            ]
        )

        return "\n".join(lines)
