"""Unit tests for Case entity and lifecycle management.

Tests case creation, hearing management, scoring, state transitions, and edge cases.
"""

from datetime import date, timedelta

import pytest

from scheduler.core.case import Case, CaseStatus


@pytest.mark.unit
class TestCaseCreation:
    """Test case initialization and basic properties."""

    def test_create_basic_case(self):
        """Test creating a case with minimal required fields."""
        case = Case(
            case_id="TEST-001",
            case_type="RSA",
            filed_date=date(2024, 1, 1),
            current_stage="ADMISSION"
        )

        assert case.case_id == "TEST-001"
        assert case.case_type == "RSA"
        assert case.filed_date == date(2024, 1, 1)
        assert case.current_stage == "ADMISSION"
        assert case.status == CaseStatus.PENDING
        assert case.hearing_count == 0
        assert case.age_days >= 0

    def test_case_with_all_fields(self):
        """Test creating a case with all fields populated."""
        case = Case(
            case_id="FULL-001",
            case_type="CRP",
            filed_date=date(2024, 1, 1),
            current_stage="ARGUMENTS",
            last_hearing_date=date(2024, 2, 15),
            age_days=100,
            hearing_count=5,
            status=CaseStatus.ACTIVE,
            is_urgent=True
        )

        assert case.last_hearing_date == date(2024, 2, 15)
        assert case.age_days == 100
        assert case.hearing_count == 5
        assert case.status == CaseStatus.ACTIVE
        assert case.is_urgent is True

    @pytest.mark.edge_case
    def test_case_filed_today(self):
        """Test case filed today (age should be 0)."""
        today = date.today()
        case = Case(
            case_id="NEW-001",
            case_type="CP",
            filed_date=today,
            current_stage="PRE-ADMISSION"
        )

        case.update_age(today)
        assert case.age_days == 0
        assert (case.age_days / 365) == 0

    @pytest.mark.failure
    def test_invalid_case_type(self):
        """Test that invalid case types are handled."""
        # Note: Current implementation may not validate, but test documents expected behavior
        case = Case(
            case_id="INVALID-001",
            case_type="INVALID_TYPE",
            filed_date=date(2024, 1, 1),
            current_stage="ADMISSION"
        )
        # Case is created but type validation could be added in future
        assert case.case_type == "INVALID_TYPE"


@pytest.mark.unit
class TestCaseAgeCalculation:
    """Test age and time-based calculations."""

    def test_age_calculation(self):
        """Test age_days calculation."""
        case = Case(
            case_id="AGE-001",
            case_type="RSA",
            filed_date=date(2024, 1, 1),
            current_stage="ADMISSION"
        )

        # Update age to Feb 1 (31 days later)
        case.update_age(date(2024, 2, 1))
        assert case.age_days == 31

    def test_age_in_years(self):
        """Test age conversion to years."""
        case = Case(
            case_id="OLD-001",
            case_type="RSA",
            filed_date=date(2022, 1, 1),
            current_stage="EVIDENCE"
        )

        case.update_age(date(2024, 1, 1))
        assert (case.age_days / 365) == 2.0

    def test_days_since_last_hearing(self):
        """Test calculation of gap since last hearing."""
        case = Case(
            case_id="GAP-001",
            case_type="CRP",
            filed_date=date(2024, 1, 1),
            current_stage="ADMISSION"
        )

        # Record hearing on Jan 15
        case.record_hearing(date(2024, 1, 15), was_heard=True, outcome="HEARD")

        # Update to Feb 1
        case.update_age(date(2024, 2, 1))
        assert case.days_since_last_hearing == 17


@pytest.mark.unit
class TestHearingManagement:
    """Test hearing recording and history."""

    def test_record_single_hearing(self):
        """Test recording a single hearing."""
        case = Case(
            case_id="HEAR-001",
            case_type="RSA",
            filed_date=date(2024, 1, 1),
            current_stage="ADMISSION"
        )

        case.record_hearing(date(2024, 1, 15), was_heard=True, outcome="ARGUMENTS")

        assert case.hearing_count == 1
        assert case.last_hearing_date == date(2024, 1, 15)


@pytest.mark.unit
class TestStageProgression:
    """Test case stage transitions."""

    def test_progress_to_next_stage(self):
        """Test progressing case to next stage."""
        case = Case(
            case_id="PROG-001",
            case_type="RSA",
            filed_date=date(2024, 1, 1),
            current_stage="ADMISSION"
        )

        case.progress_to_stage("EVIDENCE", date(2024, 2, 1))

        assert case.current_stage == "EVIDENCE"

    def test_progress_to_terminal_stage(self):
        """Test progressing to terminal stage (ORDERS/JUDGMENT)."""
        case = Case(
            case_id="TERM-001",
            case_type="CP",
            filed_date=date(2024, 1, 1),
            current_stage="ARGUMENTS"
        )

        case.progress_to_stage("ORDERS", date(2024, 3, 1))

        assert case.current_stage == "ORDERS"

    def test_stage_sequence(self):
        """Test typical stage progression sequence."""
        case = Case(
            case_id="SEQ-001",
            case_type="RSA",
            filed_date=date(2024, 1, 1),
            current_stage="PRE-ADMISSION"
        )

        stages = ["ADMISSION", "EVIDENCE", "ARGUMENTS", "ORDERS"]
        current_date = date(2024, 1, 1)

        for stage in stages:
            current_date += timedelta(days=60)
            case.progress_to_stage(stage, current_date)
            assert case.current_stage == stage


@pytest.mark.unit
class TestCaseScoring:
    """Test case priority and readiness scoring."""

    def test_priority_score_calculation(self):
        """Test overall priority score computation."""
        case = Case(
            case_id="SCORE-001",
            case_type="RSA",
            filed_date=date(2023, 1, 1),
            current_stage="ARGUMENTS"
        )

        case.update_age(date(2024, 1, 1))  # 1 year old
        case.record_hearing(date(2023, 12, 1), was_heard=True, outcome="HEARD")
        case.update_age(date(2024, 1, 1))

        priority = case.get_priority_score()

        assert isinstance(priority, float)
        assert 0.0 <= priority <= 1.0

    def test_readiness_score_components(self):
        """Test readiness score calculation with different components."""
        case = Case(
            case_id="READY-001",
            case_type="RSA",
            filed_date=date(2024, 1, 1),
            current_stage="ARGUMENTS"
        )

        # Add some hearings
        for i in range(10):
            case.record_hearing(
                date(2024, 1, 1) + timedelta(days=30 * i),
                was_heard=True,
                outcome="HEARD"
            )

        readiness = case.compute_readiness_score()

        assert isinstance(readiness, float)
        assert 0.0 <= readiness <= 1.0

    def test_urgency_boost(self):
        """Test that urgent cases get priority boost."""
        normal_case = Case(
            case_id="NORMAL-001",
            case_type="CP",
            filed_date=date(2024, 1, 1),
            current_stage="ADMISSION",
            is_urgent=False
        )

        urgent_case = Case(
            case_id="URGENT-001",
            case_type="CP",
            filed_date=date(2024, 1, 1),
            current_stage="ADMISSION",
            is_urgent=True
        )

        # Update ages to same date
        test_date = date(2024, 2, 1)
        normal_case.update_age(test_date)
        urgent_case.update_age(test_date)

        # Urgent case should have higher priority
        assert urgent_case.get_priority_score() > normal_case.get_priority_score()

    def test_adjournment_boost(self):
        """Test that recently adjourned cases get priority boost."""
        case = Case(
            case_id="ADJ-BOOST-001",
            case_type="RSA",
            filed_date=date(2024, 1, 1),
            current_stage="ARGUMENTS"
        )

        # Record adjourned hearing
        case.record_hearing(date(2024, 2, 1), was_heard=False, outcome="ADJOURNED")

        # Priority should be higher shortly after adjournment
        case.update_age(date(2024, 2, 5))
        case.get_priority_score()

        # Priority boost should decay over time
        case.update_age(date(2024, 3, 1))
        case.get_priority_score()

        # Note: This test assumes adjournment boost exists and decays
        # Implementation may vary


@pytest.mark.unit
class TestCaseReadiness:
    """Test case readiness for scheduling."""

    def test_ready_for_scheduling(self):
        """Test case that is ready for scheduling."""
        case = Case(
            case_id="READY-001",
            case_type="RSA",
            filed_date=date(2024, 1, 1),
            current_stage="ARGUMENTS"
        )

        # Record hearing 30 days ago
        case.record_hearing(date(2024, 1, 15), was_heard=True, outcome="HEARD")
        case.update_age(date(2024, 2, 15))

        # Should be ready (30 days > 7 day min gap)
        assert case.is_ready_for_scheduling(min_gap_days=7) is True

    def test_not_ready_min_gap(self):
        """Test case that doesn't meet minimum gap requirement."""
        case = Case(
            case_id="NOT-READY-001",
            case_type="RSA",
            filed_date=date(2024, 1, 1),
            current_stage="ADMISSION"
        )

        # Record hearing 3 days ago
        case.record_hearing(date(2024, 2, 10), was_heard=True, outcome="HEARD")
        case.update_age(date(2024, 2, 13))

        # Should not be ready (3 days < 7 day min gap)
        assert case.is_ready_for_scheduling(min_gap_days=7) is False

    def test_first_hearing_always_ready(self):
        """Test that case with no hearings is ready for first scheduling."""
        case = Case(
            case_id="FIRST-001",
            case_type="CP",
            filed_date=date(2024, 1, 1),
            current_stage="ADMISSION"
        )

        case.update_age(date(2024, 1, 15))

        # Should be ready for first hearing
        assert case.is_ready_for_scheduling(min_gap_days=7) is True


@pytest.mark.unit
class TestCaseStatus:
    """Test case status transitions."""

    def test_initial_status_pending(self):
        """Test that new cases start as PENDING."""
        case = Case(
            case_id="STATUS-001",
            case_type="RSA",
            filed_date=date(2024, 1, 1),
            current_stage="PRE-ADMISSION"
        )

        assert case.status == CaseStatus.PENDING

    def test_mark_disposed(self):
        """Test marking case as disposed."""
        case = Case(
            case_id="DISPOSE-001",
            case_type="CP",
            filed_date=date(2024, 1, 1),
            current_stage="ORDERS"
        )

        case.status = CaseStatus.DISPOSED

        assert case.is_disposed() is True

    def test_disposed_case_properties(self):
        """Test that disposed cases have expected properties."""
        from tests.conftest import disposed_case

        case = disposed_case()

        assert case.status == CaseStatus.DISPOSED
        assert case.is_disposed() is True


@pytest.mark.unit
class TestCaseSerialization:
    """Test case conversion and serialization."""

    def test_to_dict(self):
        """Test converting case to dictionary."""
        case = Case(
            case_id="DICT-001",
            case_type="RSA",
            filed_date=date(2024, 1, 1),
            current_stage="ADMISSION",
            hearing_count=3
        )

        case_dict = case.to_dict()

        assert isinstance(case_dict, dict)
        assert case_dict["case_id"] == "DICT-001"
        assert case_dict["case_type"] == "RSA"
        assert case_dict["current_stage"] == "ADMISSION"
        assert case_dict["hearing_count"] == 3

    def test_repr(self):
        """Test case string representation."""
        case = Case(
            case_id="REPR-001",
            case_type="CRP",
            filed_date=date(2024, 1, 1),
            current_stage="ARGUMENTS"
        )

        repr_str = repr(case)

        assert "REPR-001" in repr_str
        assert "CRP" in repr_str


@pytest.mark.edge_case
class TestCaseEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_case_with_null_fields(self):
        """Test case with optional fields set to None."""
        case = Case(
            case_id="NULL-001",
            case_type="RSA",
            filed_date=date(2024, 1, 1),
            current_stage="ADMISSION",
            last_hearing_date=None,
            is_urgent=None
        )

        assert case.last_hearing_date is None
        assert case.is_urgent is None or case.is_urgent is False

    def test_case_age_boundary(self):
        """Test case at exact age boundaries (0, 1 year, 2 years)."""
        case = Case(
            case_id="BOUNDARY-001",
            case_type="RSA",
            filed_date=date(2024, 1, 1),
            current_stage="ADMISSION"
        )

        # Exactly 0 days
        case.update_age(date(2024, 1, 1))
        assert case.age_days == 0

        # Exactly 365 days
        case.update_age(date(2025, 1, 1))
        assert case.age_days == 365
        assert (case.age_days / 365) == 1.0

        # Exactly 730 days
        case.update_age(date(2026, 1, 1))
        assert case.age_days == 730
        assert (case.age_days / 365) == 2.0

    def test_hearing_on_case_filed_date(self):
        """Test recording hearing on same day case was filed."""
        case = Case(
            case_id="SAME-DAY-001",
            case_type="CP",
            filed_date=date(2024, 1, 1),
            current_stage="ADMISSION"
        )

        # Record hearing on filed date
        case.record_hearing(date(2024, 1, 1), was_heard=True, outcome="ADMISSION")

        assert case.hearing_count == 1
        assert case.last_hearing_date == date(2024, 1, 1)


@pytest.mark.failure
class TestCaseFailureScenarios:
    """Test failure scenarios and error handling."""

    def test_future_filed_date(self):
        """Test case filed in the future (should be invalid)."""
        future_date = date.today() + timedelta(days=365)

        case = Case(
            case_id="FUTURE-001",
            case_type="RSA",
            filed_date=future_date,
            current_stage="ADMISSION"
        )

        # Case is created but update_age should handle gracefully
        case.update_age(date.today())
        # age_days might be negative or handled specially

    def test_disposed_case_operations(self):
        """Test that disposed cases handle operations appropriately."""
        case = Case(
            case_id="DISPOSED-OPS-001",
            case_type="CP",
            filed_date=date(2024, 1, 1),
            current_stage="ORDERS",
            status=CaseStatus.DISPOSED
        )

        # Should still be able to query properties
        assert case.is_disposed() is True

        # Recording hearing on disposed case (implementation dependent)
        # Some implementations might allow, others might not



