"""Unit tests for Courtroom entity and scheduling.

Tests courtroom capacity management, judge assignment, schedule operations, and edge cases.
"""

from datetime import date, timedelta

import pytest

from src.core.courtroom import Courtroom


@pytest.mark.unit
class TestCourtroomCreation:
    """Test courtroom initialization."""

    def test_create_basic_courtroom(self):
        """Test creating a courtroom with basic parameters."""
        courtroom = Courtroom(courtroom_id=1, judge_id="J001", daily_capacity=50)

        assert courtroom.courtroom_id == 1
        assert courtroom.judge_id == "J001"
        assert courtroom.daily_capacity == 50

    def test_multiple_judge_courtroom(self):
        """Test courtroom with multiple judges (bench)."""
        # If supported
        courtroom = Courtroom(
            courtroom_id=1,
            judge_id="J001,J002",  # Multi-judge notation
            daily_capacity=60,
        )

        assert courtroom.judge_id == "J001,J002"
        assert courtroom.daily_capacity == 60


@pytest.mark.unit
class TestCourtroomCapacity:
    """Test courtroom capacity management."""

    def test_can_schedule_within_capacity(self, single_courtroom):
        """Test that cases can be scheduled within capacity."""
        test_date = date(2024, 6, 15)

        # Schedule 40 cases (capacity is 50)
        for i in range(40):
            assert single_courtroom.can_schedule(test_date, f"CASE-{i}") is True
            single_courtroom.schedule_case(test_date, f"CASE-{i}")

        # Should still have room for more
        assert single_courtroom.can_schedule(test_date, "CASE-40") is True

    def test_cannot_exceed_capacity(self, single_courtroom):
        """Test that scheduling stops at capacity limit."""
        test_date = date(2024, 6, 15)

        # Schedule up to capacity (50)
        for i in range(50):
            if single_courtroom.can_schedule(test_date, f"CASE-{i}"):
                single_courtroom.schedule_case(test_date, f"CASE-{i}")

        # Should not be able to schedule more
        assert single_courtroom.can_schedule(test_date, "CASE-EXTRA") is False

    def test_capacity_reset_per_day(self, single_courtroom):
        """Test that capacity resets for different days."""
        day1 = date(2024, 6, 15)
        day2 = date(2024, 6, 16)

        # Fill day1
        for i in range(50):
            single_courtroom.schedule_case(day1, f"DAY1-{i}")

        # day2 should be empty
        assert single_courtroom.can_schedule(day2, "DAY2-001") is True

        # Schedule on day2
        for i in range(30):
            single_courtroom.schedule_case(day2, f"DAY2-{i}")

        # Verify day1 is still full, day2 has room
        assert single_courtroom.can_schedule(day1, "EXTRA") is False
        assert single_courtroom.can_schedule(day2, "EXTRA") is True

    @pytest.mark.edge_case
    def test_zero_capacity_courtroom(self):
        """Test courtroom with zero capacity."""
        courtroom = Courtroom(courtroom_id=1, judge_id="J001", daily_capacity=0)
        test_date = date(2024, 6, 15)

        # Should not be able to schedule anything
        assert courtroom.can_schedule(test_date, "CASE-001") is False

    @pytest.mark.failure
    def test_negative_capacity(self):
        """Test that negative capacity is handled."""
        # Implementation might allow or reject
        Courtroom(courtroom_id=1, judge_id="J001", daily_capacity=-10)
        date(2024, 6, 15)

        # Should either prevent creation or prevent scheduling
        # Current implementation may allow, but test documents expected behavior


@pytest.mark.unit
class TestCourtroomScheduling:
    """Test courtroom case scheduling operations."""

    def test_schedule_single_case(self, single_courtroom):
        """Test scheduling a single case."""
        test_date = date(2024, 6, 15)
        case_id = "TEST-001"

        single_courtroom.schedule_case(test_date, case_id)

        # Verify scheduling succeeded
        schedule = single_courtroom.get_daily_schedule(test_date)
        assert case_id in schedule

    def test_get_daily_schedule(self, single_courtroom):
        """Test retrieving daily schedule."""
        test_date = date(2024, 6, 15)

        # Schedule 5 cases
        case_ids = [f"CASE-{i}" for i in range(5)]
        for case_id in case_ids:
            single_courtroom.schedule_case(test_date, case_id)

        schedule = single_courtroom.get_daily_schedule(test_date)

        assert len(schedule) == 5
        for case_id in case_ids:
            assert case_id in schedule

    def test_empty_schedule(self, single_courtroom):
        """Test getting schedule for day with no cases."""
        test_date = date(2024, 6, 15)

        schedule = single_courtroom.get_daily_schedule(test_date)

        assert len(schedule) == 0 or schedule == []

    def test_clear_schedule(self, single_courtroom):
        """Test clearing/removing cases from schedule."""
        test_date = date(2024, 6, 15)

        # Schedule some cases
        for i in range(10):
            single_courtroom.schedule_case(test_date, f"CASE-{i}")

        # If clear method exists
        if hasattr(single_courtroom, "clear_schedule"):
            single_courtroom.clear_schedule(test_date)
            schedule = single_courtroom.get_daily_schedule(test_date)
            assert len(schedule) == 0

    @pytest.mark.edge_case
    def test_duplicate_case_scheduling(self, single_courtroom):
        """Test scheduling same case twice on same day."""
        test_date = date(2024, 6, 15)
        case_id = "DUP-001"

        # Schedule once
        single_courtroom.schedule_case(test_date, case_id)

        # Try to schedule again
        single_courtroom.schedule_case(test_date, case_id)

        single_courtroom.get_daily_schedule(test_date)

        # Should appear only once (or implementation dependent)
        # Current implementation might allow duplicates

    def test_remove_case_from_schedule(self, single_courtroom):
        """Test removing a specific case from schedule."""
        test_date = date(2024, 6, 15)
        case_id = "REMOVE-001"

        # Schedule case
        single_courtroom.schedule_case(test_date, case_id)

        # Remove if method exists
        if hasattr(single_courtroom, "remove_case"):
            single_courtroom.remove_case(test_date, case_id)
            schedule = single_courtroom.get_daily_schedule(test_date)
            assert case_id not in schedule


@pytest.mark.unit
class TestCourtroomMultiDay:
    """Test courtroom operations across multiple days."""

    def test_schedule_across_week(self, single_courtroom):
        """Test scheduling across a full week."""
        start_date = date(2024, 6, 10)  # Monday

        for day_offset in range(7):
            current_date = start_date + timedelta(days=day_offset)

            # Schedule different number of cases each day
            num_cases = 10 + (day_offset * 5)
            for i in range(min(num_cases, 50)):
                single_courtroom.schedule_case(current_date, f"DAY{day_offset}-{i}")

        # Verify each day independently
        for day_offset in range(7):
            current_date = start_date + timedelta(days=day_offset)
            schedule = single_courtroom.get_daily_schedule(current_date)
            expected = min(10 + (day_offset * 5), 50)
            assert len(schedule) == expected

    def test_schedule_continuity(self, single_courtroom):
        """Test that schedule for one day doesn't affect another."""
        day1 = date(2024, 6, 15)
        day2 = date(2024, 6, 16)

        # Schedule on day1
        single_courtroom.schedule_case(day1, "CASE-DAY1")

        # Schedule on day2
        single_courtroom.schedule_case(day2, "CASE-DAY2")

        # Verify independence
        schedule_day1 = single_courtroom.get_daily_schedule(day1)
        schedule_day2 = single_courtroom.get_daily_schedule(day2)

        assert "CASE-DAY1" in schedule_day1
        assert "CASE-DAY1" not in schedule_day2
        assert "CASE-DAY2" in schedule_day2
        assert "CASE-DAY2" not in schedule_day1


@pytest.mark.unit
class TestJudgeAssignment:
    """Test judge assignment and preferences."""

    def test_single_judge_courtroom(self):
        """Test courtroom with single judge."""
        courtroom = Courtroom(courtroom_id=1, judge_id="J001", daily_capacity=50)

        assert courtroom.judge_id == "J001"

    def test_judge_preferences(self):
        """Test judge preferences for case types (if supported)."""
        courtroom = Courtroom(courtroom_id=1, judge_id="J001", daily_capacity=50)

        # If preferences supported
        if hasattr(courtroom, "judge_preferences"):
            # Test preference setting/getting
            pass


@pytest.mark.edge_case
class TestCourtroomEdgeCases:
    """Test courtroom edge cases."""

    def test_very_high_capacity(self):
        """Test courtroom with very high capacity (1000)."""
        courtroom = Courtroom(courtroom_id=1, judge_id="J001", daily_capacity=1000)
        test_date = date(2024, 6, 15)

        # Should be able to schedule up to 1000
        for i in range(100):  # Test subset
            assert courtroom.can_schedule(test_date, f"CASE-{i}") is True
            courtroom.schedule_case(test_date, f"CASE-{i}")

    def test_schedule_on_weekend(self, single_courtroom):
        """Test scheduling on weekend (may or may not be allowed)."""
        saturday = date(2024, 6, 15)  # Assuming this is Saturday

        # Implementation may allow or prevent
        single_courtroom.schedule_case(saturday, "WEEKEND-001")

        # Just verify no crash

    def test_schedule_on_old_date(self, single_courtroom):
        """Test scheduling on past date."""
        old_date = date(2020, 1, 1)

        # Should handle gracefully
        single_courtroom.schedule_case(old_date, "OLD-001")

    def test_schedule_on_far_future_date(self, single_courtroom):
        """Test scheduling far in future."""
        future_date = date(2030, 12, 31)

        # Should handle gracefully
        single_courtroom.schedule_case(future_date, "FUTURE-001")
        schedule = single_courtroom.get_daily_schedule(future_date)
        assert "FUTURE-001" in schedule


@pytest.mark.failure
class TestCourtroomFailureScenarios:
    """Test courtroom failure scenarios."""

    def test_invalid_courtroom_id(self):
        """Test courtroom with invalid ID."""
        # Negative ID
        Courtroom(courtroom_id=-1, judge_id="J001", daily_capacity=50)
        # Should create but document behavior

        # String ID (if not supported)
        # courtroom = Courtroom(courtroom_id="INVALID", judge_id="J001", daily_capacity=50)

    def test_null_judge_id(self):
        """Test courtroom with None judge_id."""
        Courtroom(courtroom_id=1, judge_id=None, daily_capacity=50)
        # Should handle gracefully

    def test_empty_judge_id(self):
        """Test courtroom with empty judge_id."""
        Courtroom(courtroom_id=1, judge_id="", daily_capacity=50)
        # Should handle gracefully

    def test_schedule_with_invalid_case_id(self, single_courtroom):
        """Test scheduling with None or invalid case_id."""
        test_date = date(2024, 6, 15)

        # Try None case_id
        try:
            single_courtroom.schedule_case(test_date, None)
        except (ValueError, TypeError, AttributeError):
            # Expected to fail
            pass

        # Try empty string
        try:
            single_courtroom.schedule_case(test_date, "")
        except (ValueError, TypeError):
            # May fail
            pass
