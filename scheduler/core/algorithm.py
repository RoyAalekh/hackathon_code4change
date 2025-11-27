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
from scheduler.core.policy import SchedulerPolicy
from scheduler.simulation.allocator import CourtroomAllocator, AllocationStrategy
from scheduler.control.explainability import ExplainabilityEngine, SchedulingExplanation
from scheduler.control.overrides import (
    Override,
    OverrideType,
    JudgePreferences,
    OverrideValidator,
)
from scheduler.data.config import MIN_GAP_BETWEEN_HEARINGS


@dataclass
class SchedulingResult:
    """Result of single-day scheduling with full transparency.
    
    Attributes:
        scheduled_cases: Mapping of courtroom_id to list of scheduled cases
        explanations: Decision explanations for each case (scheduled + sample unscheduled)
        applied_overrides: List of overrides that were successfully applied
        override_rejections: Structured records for rejected overrides
        unscheduled_cases: Cases not scheduled with reasons (e.g., unripe, capacity full)
        ripeness_filtered: Count of cases filtered due to unripe status
        capacity_limited: Count of cases that didn't fit due to courtroom capacity
        scheduling_date: Date scheduled for
        policy_used: Name of scheduling policy used (FIFO, Age, Readiness)
        total_scheduled: Total number of cases scheduled (calculated)
    """
    
    # Core output
    scheduled_cases: Dict[int, List[Case]]

    # Transparency
    explanations: Dict[str, SchedulingExplanation]
    applied_overrides: List[Override]
    override_rejections: List[Dict[str, str]]

    # Diagnostics
    unscheduled_cases: List[Tuple[Case, str]]
    ripeness_filtered: int
    capacity_limited: int
    
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
        preferences: Optional[JudgePreferences] = None,
        max_explanations_unscheduled: int = 100
    ) -> SchedulingResult:
        """Schedule cases for a single day with override support.
        
        Args:
            cases: All active cases (will be filtered)
            courtrooms: Available courtrooms
            current_date: Date to schedule for
            overrides: Optional manual overrides to apply
            preferences: Optional judge preferences/constraints
            max_explanations_unscheduled: Max unscheduled cases to generate explanations for
            
        Returns:
            SchedulingResult with scheduled cases, explanations, and audit trail
        """
        # Initialize tracking
        unscheduled: List[Tuple[Case, str]] = []
        applied_overrides: List[Override] = []
        explanations: Dict[str, SchedulingExplanation] = {}
        override_rejections: List[Dict[str, str]] = []
        validated_overrides: List[Override] = []

        # Validate overrides if provided
        if overrides:
            validator = OverrideValidator()
            for override in overrides:
                if validator.validate(override):
                    validated_overrides.append(override)
                else:
                    errors = validator.get_errors()
                    rejection_reason = "; ".join(errors) if errors else "Validation failed"
                    override_rejections.append({
                        "judge": override.judge_id,
                        "context": override.override_type.value,
                        "reason": rejection_reason
                    })
                    unscheduled.append(
                        (
                            None,
                            f"Invalid override rejected (judge {override.judge_id}): "
                            f"{override.override_type.value} - {rejection_reason}"
                        )
                    )

        # Filter disposed cases
        active_cases = [c for c in cases if c.status != CaseStatus.DISPOSED]
        
        # Update age and readiness for all cases
        for case in active_cases:
            case.update_age(current_date)
            case.compute_readiness_score()
        
        # CHECKPOINT 1: Ripeness filtering with override support
        ripe_cases, ripeness_filtered = self._filter_by_ripeness(
            active_cases, current_date, validated_overrides, applied_overrides
        )
        
        # CHECKPOINT 2: Eligibility check (min gap requirement)
        eligible_cases = self._filter_eligible(ripe_cases, current_date, unscheduled)
        
        # CHECKPOINT 3: Apply judge preferences (capacity overrides tracked)
        if preferences:
            applied_overrides.extend(self._get_preference_overrides(preferences, courtrooms))
        
        # CHECKPOINT 4: Prioritize using policy
        prioritized = self.policy.prioritize(eligible_cases, current_date)
        
        # CHECKPOINT 5: Apply manual overrides (add/remove/reorder/priority)
        if validated_overrides:
            prioritized = self._apply_manual_overrides(
                prioritized, validated_overrides, applied_overrides, unscheduled, active_cases
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
        
        # Generate explanations for sample of unscheduled cases
        for case, reason in unscheduled[:max_explanations_unscheduled]:
            if case is not None:  # Skip invalid override entries
                explanation = self.explainer.explain_scheduling_decision(
                    case=case,
                    current_date=current_date,
                    scheduled=False,
                    ripeness_status=case.ripeness_status,
                    capacity_full=("Capacity" in reason),
                    below_threshold=False
                )
                explanations[case.case_id] = explanation

        self._clear_temporary_case_flags(active_cases)

        return SchedulingResult(
            scheduled_cases=scheduled_allocation,
            explanations=explanations,
            applied_overrides=applied_overrides,
            override_rejections=override_rejections,
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
            from datetime import datetime
            for courtroom_id, new_capacity in preferences.capacity_overrides.items():
                override = Override(
                    override_id=f"pref-capacity-{courtroom_id}-{preferences.judge_id}",
                    override_type=OverrideType.CAPACITY,
                    case_id="",  # Not case-specific
                    judge_id=preferences.judge_id,
                    timestamp=datetime.now(),
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
        unscheduled: List[Tuple[Case, str]],
        all_cases: List[Case]
    ) -> List[Case]:
        """Apply manual overrides (ADD_CASE, REMOVE_CASE, PRIORITY, REORDER)."""
        result = prioritized.copy()
        
        # Apply ADD_CASE overrides (insert at high priority)
        add_overrides = [o for o in overrides if o.override_type == OverrideType.ADD_CASE]
        for override in add_overrides:
            # Find case in full case list
            case_to_add = next((c for c in all_cases if c.case_id == override.case_id), None)
            if case_to_add and case_to_add not in result:
                # Insert at position 0 (highest priority) or specified position
                insert_pos = override.new_position if override.new_position is not None else 0
                result.insert(min(insert_pos, len(result)), case_to_add)
                applied_overrides.append(override)
        
        # Apply REMOVE_CASE overrides
        remove_overrides = [o for o in overrides if o.override_type == OverrideType.REMOVE_CASE]
        for override in remove_overrides:
            removed = [c for c in result if c.case_id == override.case_id]
            result = [c for c in result if c.case_id != override.case_id]
            if removed:
                applied_overrides.append(override)
                unscheduled.append((removed[0], f"Judge override: {override.reason}"))
        
        # Apply PRIORITY overrides (adjust priority scores)
        priority_overrides = [o for o in overrides if o.override_type == OverrideType.PRIORITY]
        for override in priority_overrides:
            case_to_adjust = next((c for c in result if c.case_id == override.case_id), None)
            if case_to_adjust and override.new_priority is not None:
                # Store original priority for reference
                original_priority = case_to_adjust.get_priority_score()
                # Temporarily adjust case to force re-sorting
                # Note: This is a simplification - in production might need case.set_priority_override()
                case_to_adjust._priority_override = override.new_priority
                applied_overrides.append(override)
        
        # Re-sort if priority overrides were applied
        if priority_overrides:
            result.sort(key=lambda c: getattr(c, '_priority_override', c.get_priority_score()), reverse=True)
        
        # Apply REORDER overrides (explicit positioning)
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

    @staticmethod
    def _clear_temporary_case_flags(cases: List[Case]) -> None:
        """Remove temporary scheduling flags to keep case objects clean between runs."""

        for case in cases:
            if hasattr(case, "_priority_override"):
                delattr(case, "_priority_override")
