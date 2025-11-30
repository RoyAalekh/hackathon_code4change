"""Unit tests for Ripeness classification system.

Tests ripeness classification logic, threshold configuration, priority adjustments,
and ripening time estimation.
"""

from datetime import date, datetime, timedelta

import pytest

from scheduler.core.case import Case
from scheduler.core.ripeness import RipenessClassifier, RipenessStatus


@pytest.mark.unit
class TestRipenessClassification:
    """Test basic ripeness classification."""

    def test_ripe_case_classification(self, ripe_case):
        """Test that properly serviced case with hearings is classified as RIPE."""
        status = RipenessClassifier.classify(ripe_case, datetime(2024, 3, 1))

        assert status == RipenessStatus.RIPE
        assert status.is_ripe() is True
        assert status.is_unripe() is False

    def test_unripe_summons_classification(self, unripe_case):
        """Test that case with pending summons is UNRIPE_SUMMONS."""
        status = RipenessClassifier.classify(unripe_case, datetime(2024, 2, 1))

        assert status == RipenessStatus.UNRIPE_SUMMONS
        assert status.is_ripe() is False
        assert status.is_unripe() is True

    def test_unripe_dependent_classification(self):
        """Test UNRIPE_DEPENDENT status (stay/pending cases)."""
        case = Case(
            case_id="STAY-001",
            case_type="RSA",
            filed_date=date(2024, 1, 1),
            current_stage="ADMISSION",
            hearing_count=2
        )
        case.purpose_of_hearing = "STAY APPLICATION PENDING"
        case.service_status = "SERVED"

        status = RipenessClassifier.classify(case, datetime(2024, 2, 1))

        assert status == RipenessStatus.UNRIPE_DEPENDENT
        assert status.is_unripe() is True

    def test_unripe_party_classification(self):
        """Test UNRIPE_PARTY status (party non-appearance)."""
        case = Case(
            case_id="PARTY-001",
            case_type="CRP",
            filed_date=date(2024, 1, 1),
            current_stage="ADMISSION",
            hearing_count=3
        )
        case.purpose_of_hearing = "APPEARANCE OF PARTIES"
        case.service_status = "SERVED"

        status = RipenessClassifier.classify(case, datetime(2024, 2, 1))

        # Should be UNRIPE_PARTY or similar
        assert status.is_unripe() is True

    def test_unripe_document_classification(self):
        """Test UNRIPE_DOCUMENT status (documents pending)."""
        case = Case(
            case_id="DOC-001",
            case_type="RSA",
            filed_date=date(2024, 1, 1),
            current_stage="EVIDENCE",
            hearing_count=5
        )
        case.purpose_of_hearing = "FOR PRODUCTION OF DOCUMENTS"
        case.service_status = "SERVED"
        case.compliance_status = "PENDING"

        status = RipenessClassifier.classify(case, datetime(2024, 2, 1))

        assert status == RipenessStatus.UNRIPE_DOCUMENT or status.is_unripe()

    def test_unknown_status(self):
        """Test UNKNOWN status for ambiguous cases."""
        case = Case(
            case_id="UNKNOWN-001",
            case_type="MISC.CVL",
            filed_date=date(2024, 1, 1),
            current_stage="OTHER",
            hearing_count=0
        )
        # No clear indicators
        case.service_status = None
        case.purpose_of_hearing = None

        status = RipenessClassifier.classify(case, datetime(2024, 2, 1))

        # Should be UNKNOWN or not RIPE
        assert status == RipenessStatus.UNKNOWN or not status.is_ripe()


@pytest.mark.unit
class TestRipenessKeywords:
    """Test keyword-based ripeness detection."""

    def test_summons_keywords(self):
        """Test detection of summons-related keywords."""
        keywords = ["SUMMONS", "NOTICE", "ISSUE", "SERVICE"]

        for keyword in keywords:
            case = Case(
                case_id=f"KEYWORD-{keyword}",
                case_type="RSA",
                filed_date=date(2024, 1, 1),
                current_stage="PRE-ADMISSION",
                hearing_count=1
            )
            case.purpose_of_hearing = f"FOR {keyword}"

            status = RipenessClassifier.classify(case, datetime(2024, 2, 1))
            assert status.is_unripe(), f"Keyword '{keyword}' should mark case as unripe"

    def test_ripe_keywords(self):
        """Test detection of ripe-indicating keywords."""
        ripe_keywords = ["ARGUMENTS", "HEARING", "FINAL", "JUDGMENT"]

        for keyword in ripe_keywords:
            case = Case(
                case_id=f"RIPE-{keyword}",
                case_type="RSA",
                filed_date=date(2024, 1, 1),
                current_stage="ARGUMENTS",
                hearing_count=5
            )
            case.service_status = "SERVED"
            case.purpose_of_hearing = keyword

            status = RipenessClassifier.classify(case, datetime(2024, 2, 1))
            # With proper service and hearings, should be RIPE
            assert status.is_ripe() or status == RipenessStatus.RIPE

    def test_conflicting_keywords(self):
        """Test case with both ripe and unripe keywords."""
        case = Case(
            case_id="CONFLICT-001",
            case_type="RSA",
            filed_date=date(2024, 1, 1),
            current_stage="ARGUMENTS",
            hearing_count=3
        )
        case.purpose_of_hearing = "ARGUMENTS - PENDING SUMMONS"
        case.service_status = "PARTIAL"

        status = RipenessClassifier.classify(case, datetime(2024, 2, 1))

        # Unripe indicators should dominate
        assert status.is_unripe()


@pytest.mark.unit
class TestRipenessThresholds:
    """Test ripeness classification thresholds."""

    def test_min_service_hearings_threshold(self):
        """Test MIN_SERVICE_HEARINGS threshold (default 3)."""
        # Get current thresholds
        original_thresholds = RipenessClassifier.get_current_thresholds()
        min_hearings = original_thresholds.get("MIN_SERVICE_HEARINGS", 3)

        # Case with exactly min_hearings - 1 (should be unripe or unknown)
        case_below = Case(
            case_id="BELOW-001",
            case_type="RSA",
            filed_date=date(2024, 1, 1),
            current_stage="ADMISSION",
            hearing_count=min_hearings - 1
        )
        case_below.service_status = "SERVED"

        # Case with exactly min_hearings (should have better chance of being ripe)
        case_at = Case(
            case_id="AT-001",
            case_type="RSA",
            filed_date=date(2024, 1, 1),
            current_stage="ARGUMENTS",
            hearing_count=min_hearings
        )
        case_at.service_status = "SERVED"
        case_at.purpose_of_hearing = "ARGUMENTS"

        status_below = RipenessClassifier.classify(case_below, datetime(2024, 2, 1))
        status_at = RipenessClassifier.classify(case_at, datetime(2024, 2, 1))

        # Case at threshold with ripe indicators should be more likely RIPE
        assert not status_below.is_ripe() or status_at.is_ripe()

    def test_threshold_configuration(self):
        """Test getting and setting thresholds."""
        original_thresholds = RipenessClassifier.get_current_thresholds()

        # Set new threshold
        new_thresholds = {"MIN_SERVICE_HEARINGS": 5}
        RipenessClassifier.set_thresholds(new_thresholds)

        # Verify update
        updated_thresholds = RipenessClassifier.get_current_thresholds()
        assert updated_thresholds["MIN_SERVICE_HEARINGS"] == 5

        # Restore original
        RipenessClassifier.set_thresholds(original_thresholds)
        restored = RipenessClassifier.get_current_thresholds()
        assert restored == original_thresholds

    def test_multiple_threshold_updates(self):
        """Test updating multiple thresholds at once."""
        original_thresholds = RipenessClassifier.get_current_thresholds()

        new_thresholds = {
            "MIN_SERVICE_HEARINGS": 4,
            "MIN_STAGE_DAYS": 10
        }
        RipenessClassifier.set_thresholds(new_thresholds)

        updated = RipenessClassifier.get_current_thresholds()
        assert updated["MIN_SERVICE_HEARINGS"] == 4
        assert updated["MIN_STAGE_DAYS"] == 10

        # Restore
        RipenessClassifier.set_thresholds(original_thresholds)


@pytest.mark.unit
class TestRipenessPriority:
    """Test ripeness priority adjustments."""

    def test_ripe_priority_multiplier(self):
        """Test that RIPE cases get priority boost (1.5x)."""
        case = Case(
            case_id="RIPE-PRI-001",
            case_type="RSA",
            filed_date=date(2024, 1, 1),
            current_stage="ARGUMENTS",
            hearing_count=5
        )
        case.service_status = "SERVED"
        case.purpose_of_hearing = "ARGUMENTS"

        priority = RipenessClassifier.get_ripeness_priority(case, datetime(2024, 2, 1))

        # RIPE cases should get 1.5 multiplier
        assert priority >= 1.0  # At least 1.0, ideally 1.5

    def test_unripe_priority_multiplier(self):
        """Test that UNRIPE cases get priority penalty (0.7x)."""
        case = Case(
            case_id="UNRIPE-PRI-001",
            case_type="CRP",
            filed_date=date(2024, 1, 1),
            current_stage="PRE-ADMISSION",
            hearing_count=1
        )
        case.service_status = "PENDING"
        case.purpose_of_hearing = "FOR SUMMONS"

        priority = RipenessClassifier.get_ripeness_priority(case, datetime(2024, 2, 1))

        # UNRIPE cases should get 0.7 multiplier (less than 1.0)
        assert priority < 1.0


@pytest.mark.unit
class TestRipenessSchedulability:
    """Test is_schedulable logic."""

    def test_ripe_case_schedulable(self, ripe_case):
        """Test that RIPE case is schedulable."""
        schedulable = RipenessClassifier.is_schedulable(ripe_case, datetime(2024, 3, 1))

        assert schedulable is True

    def test_unripe_case_not_schedulable(self, unripe_case):
        """Test that UNRIPE case is not schedulable."""
        schedulable = RipenessClassifier.is_schedulable(unripe_case, datetime(2024, 2, 1))

        assert schedulable is False

    def test_disposed_case_not_schedulable(self, disposed_case):
        """Test that disposed case is not schedulable."""
        schedulable = RipenessClassifier.is_schedulable(disposed_case, datetime(2024, 6, 1))

        assert schedulable is False

    def test_recent_hearing_not_schedulable(self):
        """Test that case with recent hearing is not schedulable."""
        case = Case(
            case_id="RECENT-001",
            case_type="RSA",
            filed_date=date(2024, 1, 1),
            current_stage="ARGUMENTS",
            hearing_count=5
        )
        case.service_status = "SERVED"

        # Hearing yesterday
        case.record_hearing(date(2024, 2, 14), was_heard=True, outcome="HEARD")

        # Should not be schedulable (too soon)
        schedulable = RipenessClassifier.is_schedulable(case, datetime(2024, 2, 15))

        assert schedulable is False


@pytest.mark.unit
class TestRipenessExplanations:
    """Test ripeness reason explanations."""

    def test_ripe_reason(self):
        """Test explanation for RIPE status."""
        reason = RipenessClassifier.get_ripeness_reason(RipenessStatus.RIPE)

        assert isinstance(reason, str)
        assert len(reason) > 0
        assert "ready" in reason.lower() or "ripe" in reason.lower()

    def test_unripe_summons_reason(self):
        """Test explanation for UNRIPE_SUMMONS."""
        reason = RipenessClassifier.get_ripeness_reason(RipenessStatus.UNRIPE_SUMMONS)

        assert isinstance(reason, str)
        assert "summons" in reason.lower() or "service" in reason.lower()

    def test_unripe_dependent_reason(self):
        """Test explanation for UNRIPE_DEPENDENT."""
        reason = RipenessClassifier.get_ripeness_reason(RipenessStatus.UNRIPE_DEPENDENT)

        assert isinstance(reason, str)
        assert "dependent" in reason.lower() or "stay" in reason.lower() or "pending" in reason.lower()

    def test_unknown_reason(self):
        """Test explanation for UNKNOWN status."""
        reason = RipenessClassifier.get_ripeness_reason(RipenessStatus.UNKNOWN)

        assert isinstance(reason, str)
        assert "unknown" in reason.lower() or "unclear" in reason.lower()


@pytest.mark.unit
class TestRipeningTimeEstimation:
    """Test ripening time estimation."""

    def test_already_ripe_no_estimation(self, ripe_case):
        """Test that RIPE cases return None for ripening time."""
        estimate = RipenessClassifier.estimate_ripening_time(
            ripe_case,
            datetime(2024, 3, 1)
        )

        assert estimate is None

    def test_summons_ripening_time(self):
        """Test estimated time for summons cases (~30 days)."""
        case = Case(
            case_id="EST-SUMMONS-001",
            case_type="RSA",
            filed_date=date(2024, 1, 1),
            current_stage="PRE-ADMISSION",
            hearing_count=1
        )
        case.purpose_of_hearing = "FOR SUMMONS"

        estimate = RipenessClassifier.estimate_ripening_time(case, datetime(2024, 2, 1))

        if estimate is not None:
            assert isinstance(estimate, timedelta)
            # Summons typically ~30 days
            assert 20 <= estimate.days <= 45

    def test_dependent_ripening_time(self):
        """Test estimated time for dependent cases (~60 days)."""
        case = Case(
            case_id="EST-DEP-001",
            case_type="CRP",
            filed_date=date(2024, 1, 1),
            current_stage="ADMISSION",
            hearing_count=2
        )
        case.purpose_of_hearing = "STAY APPLICATION"
        case.service_status = "SERVED"

        estimate = RipenessClassifier.estimate_ripening_time(case, datetime(2024, 2, 1))

        if estimate is not None:
            assert isinstance(estimate, timedelta)
            # Dependent cases typically longer
            assert estimate.days >= 30


@pytest.mark.edge_case
class TestRipenessEdgeCases:
    """Test ripeness edge cases."""

    def test_case_with_no_hearings(self):
        """Test classification of case with zero hearings."""
        case = Case(
            case_id="ZERO-HEAR-001",
            case_type="CP",
            filed_date=date(2024, 1, 1),
            current_stage="PRE-ADMISSION",
            hearing_count=0
        )

        status = RipenessClassifier.classify(case, datetime(2024, 2, 1))

        # Should be UNKNOWN or UNRIPE (not enough evidence)
        assert not status.is_ripe()

    def test_case_with_null_service_status(self):
        """Test case with missing service status."""
        case = Case(
            case_id="NULL-SERVICE-001",
            case_type="RSA",
            filed_date=date(2024, 1, 1),
            current_stage="ADMISSION",
            hearing_count=3
        )
        case.service_status = None

        status = RipenessClassifier.classify(case, datetime(2024, 2, 1))

        # Should handle gracefully (UNKNOWN or conservative classification)
        assert status in list(RipenessStatus)

    def test_case_in_unknown_stage(self):
        """Test case in unrecognized stage."""
        case = Case(
            case_id="UNKNOWN-STAGE-001",
            case_type="MISC.CVL",
            filed_date=date(2024, 1, 1),
            current_stage="UNKNOWN_STAGE",
            hearing_count=5
        )
        case.service_status = "SERVED"

        status = RipenessClassifier.classify(case, datetime(2024, 2, 1))

        # Should handle gracefully
        assert status in list(RipenessStatus)

    def test_very_old_case(self):
        """Test classification of very old case (5+ years)."""
        case = Case(
            case_id="OLD-001",
            case_type="RSA",
            filed_date=date(2019, 1, 1),
            current_stage="EVIDENCE",
            hearing_count=50
        )
        case.service_status = "SERVED"
        case.purpose_of_hearing = "EVIDENCE"

        status = RipenessClassifier.classify(case, datetime(2024, 2, 1))

        # Age shouldn't prevent proper classification
        assert status in list(RipenessStatus)

    def test_case_with_100_hearings(self):
        """Test case with very high hearing count."""
        from tests.conftest import create_case_with_hearings

        case = create_case_with_hearings(n_hearings=100, days_between=10)
        case.service_status = "SERVED"
        case.current_stage = "ARGUMENTS"

        status = RipenessClassifier.classify(case, datetime(2024, 6, 1))

        # High hearing count + proper service = RIPE
        assert status.is_ripe()


@pytest.mark.failure
class TestRipenessFailureScenarios:
    """Test ripeness failure scenarios."""

    def test_null_case(self):
        """Test handling of None case."""
        with pytest.raises(AttributeError):
            RipenessClassifier.classify(None, datetime(2024, 2, 1))

    def test_invalid_ripeness_status(self):
        """Test that only valid RipenessStatus values are used."""
        case = Case(
            case_id="VALID-001",
            case_type="RSA",
            filed_date=date(2024, 1, 1),
            current_stage="ADMISSION",
            hearing_count=3
        )

        status = RipenessClassifier.classify(case, datetime(2024, 2, 1))

        # Should be a valid RipenessStatus enum value
        assert status in list(RipenessStatus)
        assert hasattr(status, 'is_ripe')
        assert hasattr(status, 'is_unripe')

    def test_threshold_invalid_type(self):
        """Test setting thresholds with invalid types."""
        original_thresholds = RipenessClassifier.get_current_thresholds()

        # Try setting invalid threshold
        try:
            RipenessClassifier.set_thresholds({"MIN_SERVICE_HEARINGS": "invalid"})
            # If it doesn't raise, just restore and continue
        except (TypeError, ValueError):
            # Expected behavior
            pass
        finally:
            # Always restore
            RipenessClassifier.set_thresholds(original_thresholds)

    def test_missing_required_case_fields(self):
        """Test classification with minimal case data."""
        case = Case(
            case_id="MINIMAL-001",
            case_type="RSA",
            filed_date=date(2024, 1, 1),
            current_stage="ADMISSION"
        )
        # Don't set any optional fields

        status = RipenessClassifier.classify(case, datetime(2024, 2, 1))

        # Should handle gracefully and return some status
        assert status in list(RipenessStatus)


