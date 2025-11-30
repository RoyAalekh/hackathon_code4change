"""Scheduling policy implementations."""

from scheduler.core.policy import SchedulerPolicy
from scheduler.simulation.policies.age import AgeBasedPolicy
from scheduler.simulation.policies.fifo import FIFOPolicy
from scheduler.simulation.policies.readiness import ReadinessPolicy

# Registry of supported policies (RL removed)
POLICY_REGISTRY = {
    "fifo": FIFOPolicy,
    "age": AgeBasedPolicy,
    "readiness": ReadinessPolicy,
}


def get_policy(name: str, **kwargs):
    """Get a policy instance by name.

    Args:
        name: Policy name (fifo, age, readiness)
        **kwargs: Additional arguments passed to policy constructor
    """
    name_lower = name.lower()
    if name_lower not in POLICY_REGISTRY:
        raise ValueError(f"Unknown policy: {name}")
    return POLICY_REGISTRY[name_lower](**kwargs)


__all__ = ["SchedulerPolicy", "FIFOPolicy", "AgeBasedPolicy", "ReadinessPolicy", "get_policy"]
