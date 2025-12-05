"""Pytest configuration and shared fixtures for court scheduling tests.

Provides common fixtures for:
- Sample cases with realistic data
- Courtrooms with various configurations
- Parameter loaders
- Temporary directories
- Pre-trained RL agents
"""

import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List

import pytest

from src.core.case import Case, CaseStatus
from src.core.courtroom import Courtroom
from src.data.case_generator import CaseGenerator
from src.data.param_loader import ParameterLoader


# Test markers
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line("markers", "unit: Unit tests for individual components")
    config.addinivalue_line(
        "markers", "integration: Integration tests for multi-component workflows"
    )
    config.addinivalue_line("markers", "rl: Reinforcement learning tests")
    config.addinivalue_line("markers", "simulation: Simulation engine tests")
    config.addinivalue_line(
        "markers", "edge_case: Edge case and boundary condition tests"
    )
    config.addinivalue_line("markers", "failure: Failure scenario tests")
    config.addinivalue_line("markers", "slow: Slow-running tests (>5 seconds)")


@pytest.fixture
def sample_cases() -> List[Case]:
    """Generate 100 realistic test cases.

    Returns:
        List of 100 cases with diverse types, stages, and ages
    """
    generator = CaseGenerator(start=date(2024, 1, 1), end=date(2024, 3, 31), seed=42)
    cases = generator.generate(100, stage_mix_auto=True)
    return cases


@pytest.fixture
def small_case_set() -> List[Case]:
    """Generate 10 test cases for quick tests.

    Returns:
        List of 10 cases
    """
    generator = CaseGenerator(start=date(2024, 1, 1), end=date(2024, 1, 10), seed=42)
    cases = generator.generate(10)
    return cases


@pytest.fixture
def single_case() -> Case:
    """Create a single test case.

    Returns:
        Single Case object in ADMISSION stage
    """
    return Case(
        case_id="TEST-001",
        case_type="RSA",
        filed_date=date(2024, 1, 1),
        current_stage="ADMISSION",
        last_hearing_date=None,
        age_days=30,
        hearing_count=0,
        status=CaseStatus.PENDING,
    )


@pytest.fixture
def ripe_case() -> Case:
    """Create a case that should be classified as RIPE.

    Returns:
        Case with sufficient hearings and proper service
    """
    case = Case(
        case_id="RIPE-001",
        case_type="RSA",
        filed_date=date(2024, 1, 1),
        current_stage="ARGUMENTS",
        last_hearing_date=date(2024, 2, 1),
        age_days=90,
        hearing_count=5,
        status=CaseStatus.ACTIVE,
    )
    # Set additional attributes that may be needed
    if hasattr(case, "service_status"):
        case.service_status = "SERVED"
    if hasattr(case, "compliance_status"):
        case.compliance_status = "COMPLIED"
    return case


@pytest.fixture
def unripe_case() -> Case:
    """Create a case that should be classified as UNRIPE.

    Returns:
        Case with service pending (UNRIPE_SUMMONS)
    """
    case = Case(
        case_id="UNRIPE-001",
        case_type="CRP",
        filed_date=date(2024, 1, 1),
        current_stage="PRE-ADMISSION",
        last_hearing_date=None,
        age_days=15,
        hearing_count=1,
        status=CaseStatus.PENDING,
    )
    # Set additional attributes
    if hasattr(case, "service_status"):
        case.service_status = "PENDING"
    if hasattr(case, "last_hearing_purpose"):
        case.last_hearing_purpose = "FOR ISSUE OF SUMMONS"
    return case


@pytest.fixture
def courtrooms() -> List[Courtroom]:
    """Create 5 courtrooms with realistic configurations.

    Returns:
        List of 5 courtrooms with varied capacities
    """
    return [
        Courtroom(courtroom_id=1, judge_id="J001", daily_capacity=50),
        Courtroom(courtroom_id=2, judge_id="J002", daily_capacity=50),
        Courtroom(courtroom_id=3, judge_id="J003", daily_capacity=45),
        Courtroom(courtroom_id=4, judge_id="J004", daily_capacity=55),
        Courtroom(courtroom_id=5, judge_id="J005", daily_capacity=50),
    ]


@pytest.fixture
def single_courtroom() -> Courtroom:
    """Create a single courtroom for simple tests.

    Returns:
        Single courtroom with capacity 50
    """
    return Courtroom(courtroom_id=1, judge_id="J001", daily_capacity=50)


@pytest.fixture
def param_loader() -> ParameterLoader:
    """Create a parameter loader with default parameters.

    Returns:
        ParameterLoader instance
    """
    return ParameterLoader()


@pytest.fixture
def temp_output_dir():
    """Create a temporary output directory for test artifacts.

    Yields:
        Path to temporary directory (cleaned up after test)
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_date() -> date:
    """Standard test date for reproducibility.

    Returns:
        date(2024, 6, 15) - a Saturday in the middle of the year
    """
    return date(2024, 6, 15)


@pytest.fixture
def test_datetime() -> datetime:
    """Standard test datetime for reproducibility.

    Returns:
        datetime(2024, 6, 15, 10, 0, 0)
    """
    return datetime(2024, 6, 15, 10, 0, 0)


@pytest.fixture
def disposed_case() -> Case:
    """Create a case that has been disposed.

    Returns:
        Case in DISPOSED status
    """
    case = Case(
        case_id="DISPOSED-001",
        case_type="CP",
        filed_date=date(2024, 1, 1),
        current_stage="ORDERS",
        last_hearing_date=date(2024, 3, 15),
        age_days=180,
        hearing_count=8,
        status=CaseStatus.DISPOSED,
    )
    return case


@pytest.fixture
def aged_case() -> Case:
    """Create an old case with many hearings.

    Returns:
        Case pending for 2+ years with 20+ hearings
    """
    case = Case(
        case_id="AGED-001",
        case_type="RSA",
        filed_date=date(2022, 1, 1),
        current_stage="EVIDENCE",
        last_hearing_date=date(2024, 5, 1),
        age_days=800,
        hearing_count=25,
        status=CaseStatus.ACTIVE,
    )
    return case


@pytest.fixture
def urgent_case() -> Case:
    """Create an urgent case (filed recently, high priority).

    Returns:
        Case with urgency flag
    """
    case = Case(
        case_id="URGENT-001",
        case_type="CMP",
        filed_date=date(2024, 6, 1),
        current_stage="ADMISSION",
        last_hearing_date=None,
        age_days=5,
        hearing_count=0,
        status=CaseStatus.PENDING,
        is_urgent=True,
    )
    return case


# Helper functions for tests


def assert_valid_case(case: Case):
    """Assert that a case has all required fields and valid values.

    Args:
        case: Case to validate
    """
    assert case.case_id is not None
    assert case.case_type in ["RSA", "CRP", "RFA", "CA", "CCC", "CP", "MISC.CVL", "CMP"]
    assert case.filed_date is not None
    assert case.current_stage is not None
    assert case.age_days >= 0
    assert case.hearing_count >= 0
    assert case.status in list(CaseStatus)


def create_case_with_hearings(n_hearings: int, days_between: int = 30) -> Case:
    """Create a case with a specific number of hearings.

    Args:
        n_hearings: Number of hearings to record
        days_between: Days between each hearing

    Returns:
        Case with hearing history
    """
    case = Case(
        case_id=f"MULTI-HEARING-{n_hearings}",
        case_type="RSA",
        filed_date=date(2024, 1, 1),
        current_stage="ARGUMENTS",
        status=CaseStatus.ACTIVE,
    )

    current_date = date(2024, 1, 1)
    for i in range(n_hearings):
        current_date += timedelta(days=days_between)
        outcome = "HEARD" if i % 3 != 0 else "ADJOURNED"
        was_heard = outcome == "HEARD"
        case.record_hearing(current_date, was_heard=was_heard, outcome=outcome)

    return case
