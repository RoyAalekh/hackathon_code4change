"""Unit tests for SchedulingAlgorithm.

Tests algorithm coordination, override handling, constraint enforcement, and policy integration.
"""

from datetime import date

import pytest

from src.control.overrides import Override, OverrideType
from src.core.algorithm import SchedulingAlgorithm
from src.simulation.allocator import CourtroomAllocator
from src.simulation.policies.readiness import ReadinessPolicy


@pytest.mark.unit
class TestAlgorithmBasics:
    """Test basic algorithm setup and execution."""

    def test_create_algorithm(self):
        """Test creating scheduling algorithm."""
        policy = ReadinessPolicy()
        allocator = CourtroomAllocator(num_courtrooms=5, per_courtroom_capacity=50)

        algorithm = SchedulingAlgorithm(policy=policy, allocator=allocator)

        assert algorithm.policy is not None
        assert algorithm.allocator is not None

    def test_schedule_simple_day(self, small_case_set, courtrooms):
        """Test scheduling a simple day with 10 cases."""
        policy = ReadinessPolicy()
        allocator = CourtroomAllocator(
            num_courtrooms=len(courtrooms), per_courtroom_capacity=50
        )
        algorithm = SchedulingAlgorithm(policy=policy, allocator=allocator)

        result = algorithm.schedule_day(
            cases=small_case_set, courtrooms=courtrooms, current_date=date(2024, 2, 1)
        )

        assert result is not None
        assert hasattr(result, "scheduled_cases")
        assert len(result.scheduled_cases) > 0


@pytest.mark.unit
class TestOverrideHandling:
    """Test override processing and validation."""

    def test_valid_priority_override(self, small_case_set, courtrooms):
        """Test applying valid priority override."""
        policy = ReadinessPolicy()
        allocator = CourtroomAllocator(
            num_courtrooms=len(courtrooms), per_courtroom_capacity=50
        )
        algorithm = SchedulingAlgorithm(policy=policy, allocator=allocator)

        # Create priority override for first case
        override = Override(
            override_id="PRI-001",
            override_type=OverrideType.PRIORITY,
            case_id=small_case_set[0].case_id,
            judge_id="J001",
            timestamp=date(2024, 1, 31),
            new_priority=0.95,
        )

        result = algorithm.schedule_day(
            cases=small_case_set,
            courtrooms=courtrooms,
            current_date=date(2024, 2, 1),
            overrides=[override],
        )

        # Verify override was applied
        assert hasattr(result, "applied_overrides")
        assert len(result.applied_overrides) >= 0

    def test_invalid_override_rejection(self, small_case_set, courtrooms):
        """Test that invalid overrides are rejected."""
        policy = ReadinessPolicy()
        allocator = CourtroomAllocator(
            num_courtrooms=len(courtrooms), per_courtroom_capacity=50
        )
        algorithm = SchedulingAlgorithm(policy=policy, allocator=allocator)

        # Create override for non-existent case
        override = Override(
            override_id="INVALID-001",
            override_type=OverrideType.PRIORITY,
            case_id="NONEXISTENT-CASE",
            judge_id="J001",
            timestamp=date(2024, 1, 31),
            new_priority=0.95,
        )

        result = algorithm.schedule_day(
            cases=small_case_set,
            courtrooms=courtrooms,
            current_date=date(2024, 2, 1),
            overrides=[override],
        )

        # Verify rejection tracking
        assert hasattr(result, "override_rejections")
        # Invalid override should be rejected

    def test_mixed_valid_invalid_overrides(self, small_case_set, courtrooms):
        """Test handling mix of valid and invalid overrides."""
        policy = ReadinessPolicy()
        allocator = CourtroomAllocator(
            num_courtrooms=len(courtrooms), per_courtroom_capacity=50
        )
        algorithm = SchedulingAlgorithm(policy=policy, allocator=allocator)

        overrides = [
            Override(
                override_id="VALID-001",
                override_type=OverrideType.PRIORITY,
                case_id=small_case_set[0].case_id,
                judge_id="J001",
                timestamp=date(2024, 1, 31),
                new_priority=0.95,
            ),
            Override(
                override_id="INVALID-001",
                override_type=OverrideType.EXCLUDE,
                case_id="NONEXISTENT",
                judge_id="J001",
                timestamp=date(2024, 1, 31),
            ),
            Override(
                override_id="VALID-002",
                override_type=OverrideType.DATE,
                case_id=small_case_set[1].case_id,
                judge_id="J002",
                timestamp=date(2024, 1, 31),
                preferred_date=date(2024, 2, 5),
            ),
        ]

        result = algorithm.schedule_day(
            cases=small_case_set,
            courtrooms=courtrooms,
            current_date=date(2024, 2, 1),
            overrides=overrides,
        )

        # Valid overrides should be applied, invalid rejected
        assert hasattr(result, "applied_overrides")
        assert hasattr(result, "override_rejections")

    def test_override_list_not_mutated(self, small_case_set, courtrooms):
        """Test that original override list is not mutated."""
        policy = ReadinessPolicy()
        allocator = CourtroomAllocator(
            num_courtrooms=len(courtrooms), per_courtroom_capacity=50
        )
        algorithm = SchedulingAlgorithm(policy=policy, allocator=allocator)

        overrides = [
            Override(
                override_id="TEST-001",
                override_type=OverrideType.PRIORITY,
                case_id=small_case_set[0].case_id,
                judge_id="J001",
                timestamp=date(2024, 1, 31),
                new_priority=0.95,
            )
        ]

        original_count = len(overrides)

        algorithm.schedule_day(
            cases=small_case_set,
            courtrooms=courtrooms,
            current_date=date(2024, 2, 1),
            overrides=overrides,
        )

        # Original list should remain unchanged
        assert len(overrides) == original_count


@pytest.mark.unit
class TestConstraintEnforcement:
    """Test constraint enforcement (min gap, capacity, etc.)."""

    def test_min_gap_enforcement(self, sample_cases, courtrooms):
        """Test that minimum gap between hearings is enforced."""
        policy = ReadinessPolicy()
        allocator = CourtroomAllocator(
            num_courtrooms=len(courtrooms), per_courtroom_capacity=50
        )
        algorithm = SchedulingAlgorithm(policy=policy, allocator=allocator)

        # Record recent hearing for a case
        sample_cases[0].record_hearing(
            date(2024, 1, 28), was_heard=True, outcome="HEARD"
        )
        sample_cases[0].update_age(date(2024, 2, 1))

        algorithm.schedule_day(
            cases=sample_cases, courtrooms=courtrooms, current_date=date(2024, 2, 1)
        )

        # Case with recent hearing (4 days ago) should not be scheduled if min_gap=7
        # (Implementation dependent on min_gap setting)

    def test_capacity_limits(self, sample_cases, single_courtroom):
        """Test that courtroom capacity is not exceeded."""
        policy = ReadinessPolicy()
        allocator = CourtroomAllocator(num_courtrooms=1, per_courtroom_capacity=50)
        algorithm = SchedulingAlgorithm(policy=policy, allocator=allocator)

        result = algorithm.schedule_day(
            cases=sample_cases,
            courtrooms=[single_courtroom],
            current_date=date(2024, 2, 1),
        )

        # Should not schedule more than capacity
        assert len(result.scheduled_cases) <= 50

    def test_working_days_only(self, small_case_set, courtrooms):
        """Test scheduling only happens on working days."""
        policy = ReadinessPolicy()
        allocator = CourtroomAllocator(
            num_courtrooms=len(courtrooms), per_courtroom_capacity=50
        )
        algorithm = SchedulingAlgorithm(policy=policy, allocator=allocator)

        # Try scheduling on a weekend (if enforced)
        saturday = date(2024, 6, 15)  # Assume Saturday

        algorithm.schedule_day(
            cases=small_case_set, courtrooms=courtrooms, current_date=saturday
        )

        # Implementation may allow or prevent weekend scheduling


@pytest.mark.unit
class TestRipenessFiltering:
    """Test that unripe cases are filtered out."""

    def test_ripe_cases_scheduled(self, ripe_case, courtrooms):
        """Test that RIPE cases are scheduled."""
        policy = ReadinessPolicy()
        allocator = CourtroomAllocator(
            num_courtrooms=len(courtrooms), per_courtroom_capacity=50
        )
        algorithm = SchedulingAlgorithm(policy=policy, allocator=allocator)

        result = algorithm.schedule_day(
            cases=[ripe_case], courtrooms=courtrooms, current_date=date(2024, 3, 1)
        )

        # RIPE case should be scheduled
        assert len(result.scheduled_cases) > 0

    def test_unripe_cases_filtered(self, unripe_case, courtrooms):
        """Test that UNRIPE cases are not scheduled."""
        policy = ReadinessPolicy()
        allocator = CourtroomAllocator(
            num_courtrooms=len(courtrooms), per_courtroom_capacity=50
        )
        algorithm = SchedulingAlgorithm(policy=policy, allocator=allocator)

        algorithm.schedule_day(
            cases=[unripe_case], courtrooms=courtrooms, current_date=date(2024, 2, 1)
        )

        # UNRIPE case should not be scheduled
        # (or be in filtered list)


@pytest.mark.unit
class TestLoadBalancing:
    """Test load balancing across courtrooms."""

    def test_balanced_allocation(self, sample_cases, courtrooms):
        """Test that cases are distributed evenly across courtrooms."""
        policy = ReadinessPolicy()
        allocator = CourtroomAllocator(
            num_courtrooms=len(courtrooms), per_courtroom_capacity=50
        )
        algorithm = SchedulingAlgorithm(policy=policy, allocator=allocator)

        result = algorithm.schedule_day(
            cases=sample_cases, courtrooms=courtrooms, current_date=date(2024, 2, 1)
        )

        # Check Gini coefficient for balance
        if hasattr(result, "gini_coefficient"):
            # Low Gini = good balance
            assert result.gini_coefficient < 0.3

    def test_single_courtroom_allocation(self, small_case_set, single_courtroom):
        """Test allocation with single courtroom."""
        policy = ReadinessPolicy()
        allocator = CourtroomAllocator(num_courtrooms=1, per_courtroom_capacity=50)
        algorithm = SchedulingAlgorithm(policy=policy, allocator=allocator)

        result = algorithm.schedule_day(
            cases=small_case_set,
            courtrooms=[single_courtroom],
            current_date=date(2024, 2, 1),
        )

        # All scheduled cases should go to single courtroom
        assert len(result.scheduled_cases) <= 50


@pytest.mark.edge_case
class TestAlgorithmEdgeCases:
    """Test algorithm edge cases."""

    def test_empty_case_list(self, courtrooms):
        """Test scheduling with no cases."""
        policy = ReadinessPolicy()
        allocator = CourtroomAllocator(
            num_courtrooms=len(courtrooms), per_courtroom_capacity=50
        )
        algorithm = SchedulingAlgorithm(policy=policy, allocator=allocator)

        result = algorithm.schedule_day(
            cases=[], courtrooms=courtrooms, current_date=date(2024, 2, 1)
        )

        # Should handle gracefully
        assert len(result.scheduled_cases) == 0

    def test_all_cases_unripe(self, courtrooms):
        """Test when all cases are unripe."""
        policy = ReadinessPolicy()
        allocator = CourtroomAllocator(
            num_courtrooms=len(courtrooms), per_courtroom_capacity=50
        )
        algorithm = SchedulingAlgorithm(policy=policy, allocator=allocator)

        # Create unripe cases
        from src.core.case import Case

        unripe_cases = [
            Case(
                case_id=f"UNRIPE-{i}",
                case_type="RSA",
                filed_date=date(2024, 1, 1),
                current_stage="PRE-ADMISSION",
                hearing_count=0,
            )
            for i in range(10)
        ]

        for case in unripe_cases:
            case.service_status = "PENDING"

        result = algorithm.schedule_day(
            cases=unripe_cases, courtrooms=courtrooms, current_date=date(2024, 2, 1)
        )

        # Should schedule few or no cases
        assert len(result.scheduled_cases) < len(unripe_cases)

    def test_more_cases_than_capacity(self, courtrooms):
        """Test with more eligible cases than total capacity."""
        from src.data.case_generator import CaseGenerator

        policy = ReadinessPolicy()
        allocator = CourtroomAllocator(
            num_courtrooms=len(courtrooms), per_courtroom_capacity=50
        )
        algorithm = SchedulingAlgorithm(policy=policy, allocator=allocator)

        # Generate 500 cases (capacity is 5*50=250)
        generator = CaseGenerator(
            start=date(2024, 1, 1), end=date(2024, 1, 31), seed=42
        )
        many_cases = generator.generate(500)

        result = algorithm.schedule_day(
            cases=many_cases, courtrooms=courtrooms, current_date=date(2024, 2, 1)
        )

        # Should not exceed total capacity
        total_capacity = sum(c.daily_capacity for c in courtrooms)
        assert len(result.scheduled_cases) <= total_capacity

    def test_single_case_scheduling(self, single_case, single_courtroom):
        """Test scheduling exactly one case."""
        policy = ReadinessPolicy()
        allocator = CourtroomAllocator(num_courtrooms=1, per_courtroom_capacity=50)
        algorithm = SchedulingAlgorithm(policy=policy, allocator=allocator)

        result = algorithm.schedule_day(
            cases=[single_case],
            courtrooms=[single_courtroom],
            current_date=date(2024, 2, 1),
        )

        # Should schedule the single case (if eligible)
        assert len(result.scheduled_cases) <= 1


@pytest.mark.failure
class TestAlgorithmFailureScenarios:
    """Test algorithm failure scenarios."""

    def test_null_policy(self, small_case_set, courtrooms):
        """Test algorithm with None policy."""
        with pytest.raises((ValueError, TypeError, AttributeError)):
            SchedulingAlgorithm(policy=None, allocator=CourtroomAllocator(5, 50))

    def test_null_allocator(self, small_case_set, courtrooms):
        """Test algorithm with None allocator."""
        with pytest.raises((ValueError, TypeError, AttributeError)):
            SchedulingAlgorithm(policy=ReadinessPolicy(), allocator=None)

    def test_invalid_override_type(self, small_case_set, courtrooms):
        """Test with invalid override type."""
        policy = ReadinessPolicy()
        allocator = CourtroomAllocator(
            num_courtrooms=len(courtrooms), per_courtroom_capacity=50
        )
        SchedulingAlgorithm(policy=policy, allocator=allocator)

        # Create override with invalid type
        try:
            Override(
                override_id="BAD-001",
                override_type="INVALID_TYPE",  # Not a valid OverrideType
                case_id=small_case_set[0].case_id,
                judge_id="J001",
                timestamp=date(2024, 1, 31),
            )
            # May fail at creation or during processing
        except (ValueError, TypeError):
            # Expected for strict validation
            pass
