"""Basic metrics for scheduler evaluation.

These helpers avoid heavy dependencies and can be used by scripts.
"""
from __future__ import annotations

from typing import Iterable, List, Tuple


def gini(values: Iterable[float]) -> float:
    """Compute the Gini coefficient for a non-negative list of values.

    Args:
        values: Sequence of non-negative numbers

    Returns:
        Gini coefficient in [0, 1]
    """
    vals = [v for v in values if v is not None]
    n = len(vals)
    if n == 0:
        return 0.0
    if min(vals) < 0:
        raise ValueError("Gini expects non-negative values")
    sorted_vals = sorted(vals)
    cum = 0.0
    for i, x in enumerate(sorted_vals, start=1):
        cum += i * x
    total = sum(sorted_vals)
    if total == 0:
        return 0.0
    # Gini formula: (2*sum(i*x_i)/(n*sum(x)) - (n+1)/n)
    return (2 * cum) / (n * total) - (n + 1) / n


def utilization(total_scheduled: int, capacity: int) -> float:
    """Compute utilization as scheduled/capacity.

    Args:
        total_scheduled: Number of scheduled hearings
        capacity: Total available slots
    """
    if capacity <= 0:
        return 0.0
    return min(1.0, total_scheduled / capacity)


def urgency_sla(records: List[Tuple[bool, int]], days: int = 7) -> float:
    """Compute SLA for urgent cases.

    Args:
        records: List of tuples (is_urgent, working_day_delay)
        days: SLA threshold in working days

    Returns:
        Proportion of urgent cases within SLA (0..1)
    """
    urgent = [delay for is_urgent, delay in records if is_urgent]
    if not urgent:
        return 1.0
    within = sum(1 for d in urgent if d <= days)
    return within / len(urgent)
