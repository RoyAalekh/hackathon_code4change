"""Scheduling policy implementations."""
from scheduler.simulation.policies.fifo import FIFOPolicy
from scheduler.simulation.policies.age import AgeBasedPolicy
from scheduler.simulation.policies.readiness import ReadinessPolicy

POLICY_REGISTRY = {
    "fifo": FIFOPolicy,
    "age": AgeBasedPolicy,
    "readiness": ReadinessPolicy,
}

def get_policy(name: str):
    name_lower = name.lower()
    if name_lower not in POLICY_REGISTRY:
        raise ValueError(f"Unknown policy: {name}")
    return POLICY_REGISTRY[name_lower]()

__all__ = ["FIFOPolicy", "AgeBasedPolicy", "ReadinessPolicy", "get_policy"]