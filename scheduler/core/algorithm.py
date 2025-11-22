"""Core scheduling algorithm with override mechanism.

This module provides the standalone scheduling algorithm that can be used by:
- Simulation engine (repeated daily calls)
- CLI interface (single-day scheduling)
- Web dashboard (API backend)

The algorithm accepts cases, courtrooms, date, policy, and optional overrides,
then returns scheduled cause list with explanations and audit trail.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Tuple

from scheduler.core.case import Case, CaseStatus
from scheduler.core.courtroom import Courtroom
from scheduler.core.ripeness import RipenessClassifier, RipenessStatus
from scheduler.simulation.policies import SchedulerPolicy
from scheduler.simulation.allocator import CourtroomAllocator, AllocationStrategy
from scheduler.control.explainability import ExplainabilityEngine, SchedulingExplanation
from scheduler.control.overrides import (
    Override,
    OverrideType,
    JudgePreferences,
)
from scheduler.data.config import MIN_GAP_BETWEEN_HEARINGS


@dataclass
class SchedulingResult:
    """Result of single-day scheduling with full transparency."""
    
    # Core output
    scheduled_cases: Dict[int, List[Case]]  # courtroom_id -> cases
    
    # Transparency
    explanations: Dict[str, SchedulingExplanation]  # case_id -> explanation
    applied_overrides: List[Override]  # Overrides that were applied
    
    # Diagnostics
    unscheduled_cases: List[Tuple[Case, str]]  # (case, reason)
    ripeness_filtered: int  # Count of unripe cases filtered
    capacity_limited: int  # Cases that couldn't fit due to capacity
    
    # Metadata
    scheduling_date: date
    policy_used: str
    total_scheduled: int = field(init=False)
    
    def __post_init__(self):
        """Calculate derived fields."""
        self.total_scheduled = sum(len(cases) for cases in self.scheduled_cases.values())


class SchedulingAlgorithm:
    """Core scheduling algorithm with override support.
    
    This is the main product - a clean, reusable scheduling algorithm that:
    1. Filters cases by ripeness and eligibility
    2. Applies judge preferences and manual overrides
    3. Prioritizes cases using selected policy
    4. Allocates cases to courtrooms with load balancing
    5. Generates explanations for all decisions
    
    Usage:
        algorithm = SchedulingAlgorithm(policy=readiness_policy, allocator=allocator)
        result = algorithm.schedule_day(
            cases=active_cases,
            courtrooms=courtrooms,
            current_date=date(2024, 3, 15),
            overrides=judge_overrides,
            preferences=judge_prefs
        )
    """
    
    def __init__(
        self,
        policy: SchedulerPolicy,
        allocator: Optional[CourtroomAllocator] = None,
        min_gap_days: int = MIN_GAP_BETWEEN_HEARINGS
    ):
        """Initialize algorithm with policy and allocator.
        
        Args:
            policy: Scheduling policy (FIFO, Age, Readiness)
            allocator: Courtroom allocator (defaults to load-balanced)
            min_gap_days: Minimum days between hearings for a case
        """
        self.policy = policy
        self.allocator = allocator
        self.min_gap_days = min_gap_days
        self.explainer = ExplainabilityEngine()
    
    def schedule_day(
        self,
        cases: List[Case],
        courtrooms: List[Courtroom],
        current_date: date,
        overrides: Optional[List[Override]] = None,
        preferences: Optional[JudgePreferences] = None
    ) -> SchedulingResult:
        """Schedule cases for a single day with override support.
        
        Args:
            cases: All active cases (will be filtered)
            courtrooms: Available courtrooms
            current_date: Date to schedule for
            overrides: Optional manual overrides to apply
            preferences: Optional judge preferences/constraints
            
        Returns:
            SchedulingResult with scheduled cases, explanations, and audit trail
        """
        # Initialize tracking
        unscheduled: List[Tuple[Case, str]] = []
        applied_overrides: List[Override] = []
        explanations: Dict[str, SchedulingExplanation] = {}
        
        # Filter disposed cases
        active_cases = [c for c in cases if c.status != CaseStatus.DISPOSED]
        
        # Update age and readiness for all cases
        for case in active_cases:
            case.update_age(current_date)
            case.compute_readiness_score()
        
        # CHECKPOINT 1: Ripeness filtering with override support
        ripe_cases, ripeness_filtered = self._filter_by_ripeness(
            active_cases, current_date, overrides, applied_overrides
        )
        
        # CHECKPOINT 2: Eligibility check (min gap requirement)
        eligible_cases = self._filter_eligible(ripe_cases, current_date, unscheduled)
        
        # CHECKPOINT 3: Apply judge preferences (capacity overrides tracked)
        if preferences:
            applied_overrides.extend(self._get_preference_overrides(preferences, courtrooms))
        
        # CHECKPOINT 4: Prioritize using policy
        prioritized = self.policy.prioritize(eligible_cases, current_date)
        
        # CHECKPOINT 5: Apply manual overrides (add/remove/reorder)
        if overrides:
            prioritized = self._apply_manual_overrides(
                prioritized, overrides, applied_overrides, unscheduled
            )
        
        # CHECKPOINT 6: Allocate to courtrooms
        scheduled_allocation, capacity_limited = self._allocate_cases(
            prioritized, courtrooms, current_date, preferences
        )
        
        # Track capacity-limited cases
        total_scheduled = sum(len(cases) for cases in scheduled_allocation.values())
        for case in prioritized[total_scheduled:]:
            unscheduled.append((case, "Capacity exceeded - all courtrooms full"))
        
        # CHECKPOINT 7: Generate explanations for scheduled cases
        for courtroom_id, cases_in_room in scheduled_allocation.items():
            for case in cases_in_room:
                explanation = self.explainer.explain_scheduling_decision(
                    case=case,
                    current_date=current_date,
                    scheduled=True,
                    ripeness_status=case.ripeness_status,
                    priority_score=case.get_priority_score(),
                    courtroom_id=courtroom_id
                )
                explanations[case.case_id] = explanation
        
        # Generate explanations for sample of unscheduled cases (top 10)
        for case, reason in unscheduled[:10]:
            explanation = self.explainer.explain_scheduling_decision(
                case=case,
                current_date=current_date,
                scheduled=False,
                ripeness_status=case.ripeness_status,
                capacity_full=("Capacity" in reason),
                below_threshold=False
            )
            explanations[case.case_id] = explanation
        
        return SchedulingResult(
            scheduled_cases=scheduled_allocation,
            explanations=explanations,
            applied_overrides=applied_overrides,
            unscheduled_cases=unscheduled,
            ripeness_filtered=ripeness_filtered,
            capacity_limited=capacity_limited,
            scheduling_date=current_date,
            policy_used=self.policy.get_name()
        )
    
    def _filter_by_ripeness(
        self,
        cases: List[Case],
        current_date: date,
        overrides: Optional[List[Override]],
        applied_overrides: List[Override]
    ) -> Tuple[List[Case], int]:
        """Filter cases by ripeness with override support."""
        # Build override lookup
        ripeness_overrides = {}
        if overrides:
            for override in overrides:
                if override.override_type == OverrideType.RIPENESS:
                    ripeness_overrides[override.case_id] = override.make_ripe
        
        ripe_cases = []
        filtered_count = 0
        
        for case in cases:
            # Check for ripeness override
            if case.case_id in ripeness_overrides:
                if ripeness_overrides[case.case_id]:
                    case.mark_ripe(current_date)
                    ripe_cases.append(case)
                    # Track override application
                    override = next(o for o in overrides if o.case_id == case.case_id and o.override_type == OverrideType.RIPENESS)
                    applied_overrides.append(override)
                else:
                    case.mark_unripe(RipenessStatus.UNRIPE_DEPENDENT, "Judge override", current_date)
                    filtered_count += 1
                continue
            
            # Normal ripeness classification
            ripeness = RipenessClassifier.classify(case, current_date)
            
            if ripeness.value != case.ripeness_status:
                if ripeness.is_ripe():
                    case.mark_ripe(current_date)
                else:
                    reason = RipenessClassifier.get_ripeness_reason(ripeness)
                    case.mark_unripe(ripeness, reason, current_date)
            
            if ripeness.is_ripe():
                ripe_cases.append(case)
            else:
                filtered_count += 1
        
        return ripe_cases, filtered_count
    
    def _filter_eligible(
        self,
        cases: List[Case],
        current_date: date,
        unscheduled: List[Tuple[Case, str]]
    ) -> List[Case]:
        """Filter cases that meet minimum gap requirement."""
        eligible = []
        for case in cases:
            if case.is_ready_for_scheduling(self.min_gap_days):
                eligible.append(case)
            else:
                reason = f"Min gap not met - last hearing {case.days_since_last_hearing}d ago (min {self.min_gap_days}d)"
                unscheduled.append((case, reason))
        return eligible
    
    def _get_preference_overrides(
        self,
        preferences: JudgePreferences,
        courtrooms: List[Courtroom]
    ) -> List[Override]:
        """Extract overrides from judge preferences for audit trail."""
        overrides = []
        
        if preferences.capacity_overrides:
            for courtroom_id, new_capacity in preferences.capacity_overrides.items():
                override = Override(
                    override_type=OverrideType.CAPACITY,
                    courtroom_id=courtroom_id,
                    new_capacity=new_capacity,
                    reason="Judge preference"
                )
                overrides.append(override)
        
        return overrides
    
    def _apply_manual_overrides(
        self,
        prioritized: List[Case],
        overrides: List[Override],
        applied_overrides: List[Override],
        unscheduled: List[Tuple[Case, str]]
    ) -> List[Case]:
        """Apply manual overrides (REMOVE_CASE, REORDER)."""
        result = prioritized.copy()
        
        # Apply REMOVE_CASE overrides
        remove_overrides = [o for o in overrides if o.override_type == OverrideType.REMOVE_CASE]
        for override in remove_overrides:
            removed = [c for c in result if c.case_id == override.case_id]
            result = [c for c in result if c.case_id != override.case_id]
            if removed:
                applied_overrides.append(override)
                unscheduled.append((removed[0], f"Judge override: {override.reason}"))
        
        # Apply REORDER overrides
        reorder_overrides = [o for o in overrides if o.override_type == OverrideType.REORDER]
        for override in reorder_overrides:
            if override.case_id and override.new_position is not None:
                case_to_move = next((c for c in result if c.case_id == override.case_id), None)
                if case_to_move and 0 <= override.new_position < len(result):
                    result.remove(case_to_move)
                    result.insert(override.new_position, case_to_move)
                    applied_overrides.append(override)
        
        return result
    
    def _allocate_cases(
        self,
        prioritized: List[Case],
        courtrooms: List[Courtroom],
        current_date: date,
        preferences: Optional[JudgePreferences]
    ) -> Tuple[Dict[int, List[Case]], int]:
        """Allocate prioritized cases to courtrooms."""
        # Calculate total capacity (with preference overrides)
        total_capacity = 0
        for room in courtrooms:
            if preferences and room.courtroom_id in preferences.capacity_overrides:
                total_capacity += preferences.capacity_overrides[room.courtroom_id]
            else:
                total_capacity += room.get_capacity_for_date(current_date)
        
        # Limit cases to total capacity
        cases_to_allocate = prioritized[:total_capacity]
        capacity_limited = len(prioritized) - len(cases_to_allocate)
        
        # Use allocator to distribute
        if self.allocator:
            case_to_courtroom = self.allocator.allocate(cases_to_allocate, current_date)
        else:
            # Fallback: round-robin
            case_to_courtroom = {}
            for i, case in enumerate(cases_to_allocate):
                room_id = courtrooms[i % len(courtrooms)].courtroom_id
                case_to_courtroom[case.case_id] = room_id
        
        # Build allocation dict
        allocation: Dict[int, List[Case]] = {r.courtroom_id: [] for r in courtrooms}
        for case in cases_to_allocate:
            if case.case_id in case_to_courtroom:
                courtroom_id = case_to_courtroom[case.case_id]
                allocation[courtroom_id].append(case)
        
        return allocation, capacity_limited
