"""Unit tests for FIFO (First-In-First-Out) scheduling policy.

Tests that cases are ordered by filing date.
"""

from datetime import date

import pytest

from src.core.case import Case
from src.simulation.policies.fifo import FIFOPolicy


@pytest.mark.unit
class TestFIFOPolicy:
    """Test FIFO policy case ordering."""

    def test_fifo_ordering(self):
        """Test that cases are ordered by filed_date (oldest first)."""
        policy = FIFOPolicy()

        # Create cases with different filing dates
        cases = [
            Case(
                case_id="C3",
                case_type="RSA",
                filed_date=date(2024, 3, 1),
                current_stage="ADMISSION",
            ),
            Case(
                case_id="C1",
                case_type="CRP",
                filed_date=date(2024, 1, 1),
                current_stage="ADMISSION",
            ),
            Case(
                case_id="C2",
                case_type="CA",
                filed_date=date(2024, 2, 1),
                current_stage="ADMISSION",
            ),
        ]

        prioritized = policy.prioritize(cases, current_date=date(2024, 4, 1))

        # Should be ordered: C1 (Jan 1), C2 (Feb 1), C3 (Mar 1)
        assert prioritized[0].case_id == "C1"
        assert prioritized[1].case_id == "C2"
        assert prioritized[2].case_id == "C3"

    def test_same_filing_date_tie_breaking(self):
        """Test tie-breaking when cases filed on same date."""
        policy = FIFOPolicy()

        cases = [
            Case(
                case_id="C-B",
                case_type="RSA",
                filed_date=date(2024, 1, 1),
                current_stage="ADMISSION",
            ),
            Case(
                case_id="C-A",
                case_type="CRP",
                filed_date=date(2024, 1, 1),
                current_stage="ADMISSION",
            ),
            Case(
                case_id="C-C",
                case_type="CA",
                filed_date=date(2024, 1, 1),
                current_stage="ADMISSION",
            ),
        ]

        prioritized = policy.prioritize(cases, current_date=date(2024, 2, 1))

        # Tie-breaking typically by case_id (alphabetical or insertion order)
        # Exact order depends on implementation
        assert len(prioritized) == 3

    def test_empty_case_list(self):
        """Test FIFO with empty case list."""
        policy = FIFOPolicy()

        prioritized = policy.prioritize([], current_date=date(2024, 1, 1))

        assert prioritized == []

    def test_single_case(self):
        """Test FIFO with single case."""
        policy = FIFOPolicy()

        cases = [
            Case(
                case_id="ONLY",
                case_type="RSA",
                filed_date=date(2024, 1, 1),
                current_stage="ADMISSION",
            )
        ]

        prioritized = policy.prioritize(cases, current_date=date(2024, 2, 1))

        assert len(prioritized) == 1
        assert prioritized[0].case_id == "ONLY"

    def test_already_sorted(self):
        """Test FIFO when cases already sorted."""
        policy = FIFOPolicy()

        cases = [
            Case(
                case_id="C1",
                case_type="RSA",
                filed_date=date(2024, 1, 1),
                current_stage="ADMISSION",
            ),
            Case(
                case_id="C2",
                case_type="CRP",
                filed_date=date(2024, 2, 1),
                current_stage="ADMISSION",
            ),
            Case(
                case_id="C3",
                case_type="CA",
                filed_date=date(2024, 3, 1),
                current_stage="ADMISSION",
            ),
        ]

        prioritized = policy.prioritize(cases, current_date=date(2024, 4, 1))

        # Should remain in same order
        assert prioritized[0].case_id == "C1"
        assert prioritized[1].case_id == "C2"
        assert prioritized[2].case_id == "C3"

    def test_reverse_sorted(self):
        """Test FIFO when cases reverse sorted."""
        policy = FIFOPolicy()

        cases = [
            Case(
                case_id="C3",
                case_type="RSA",
                filed_date=date(2024, 3, 1),
                current_stage="ADMISSION",
            ),
            Case(
                case_id="C2",
                case_type="CRP",
                filed_date=date(2024, 2, 1),
                current_stage="ADMISSION",
            ),
            Case(
                case_id="C1",
                case_type="CA",
                filed_date=date(2024, 1, 1),
                current_stage="ADMISSION",
            ),
        ]

        prioritized = policy.prioritize(cases, current_date=date(2024, 4, 1))

        # Should be reversed
        assert prioritized[0].case_id == "C1"
        assert prioritized[1].case_id == "C2"
        assert prioritized[2].case_id == "C3"

    def test_large_case_set(self):
        """Test FIFO with large number of cases."""
        from src.data.case_generator import CaseGenerator

        policy = FIFOPolicy()
        generator = CaseGenerator(
            start=date(2024, 1, 1), end=date(2024, 12, 31), seed=42
        )
        cases = generator.generate(1000)

        prioritized = policy.prioritize(cases, current_date=date(2025, 1, 1))

        # Verify ordering (first should be oldest)
        for i in range(len(prioritized) - 1):
            assert prioritized[i].filed_date <= prioritized[i + 1].filed_date
