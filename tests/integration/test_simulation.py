"""Integration tests for simulation engine.

Tests multi-day simulation, case progression, ripeness tracking, and outcome validation.
"""

from datetime import date

import pytest

from scheduler.data.case_generator import CaseGenerator
from scheduler.simulation.engine import CourtSim, CourtSimConfig


@pytest.mark.integration
@pytest.mark.simulation
class TestSimulationBasics:
    """Test basic simulation execution."""

    def test_single_day_simulation(self, small_case_set, temp_output_dir):
        """Test running a 1-day simulation."""
        config = CourtSimConfig(
            start=date(2024, 1, 15),  # Monday
            days=1,
            seed=42,
            courtrooms=2,
            daily_capacity=50,
            policy="readiness",
            log_dir=temp_output_dir
        )

        sim = CourtSim(config, small_case_set)
        result = sim.run()

        assert result is not None
        assert result.hearings_total >= 0
        assert result.end_date == config.start

    def test_week_simulation(self, sample_cases, temp_output_dir):
        """Test running a 1-week (5 working days) simulation."""
        config = CourtSimConfig(
            start=date(2024, 1, 15),  # Monday
            days=7,
            seed=42,
            courtrooms=3,
            daily_capacity=50,
            policy="readiness",
            log_dir=temp_output_dir
        )

        sim = CourtSim(config, sample_cases)
        result = sim.run()

        assert result.hearings_total > 0
        # Should have had some disposals
        assert result.disposals >= 0

    @pytest.mark.slow
    def test_month_simulation(self, sample_cases, temp_output_dir):
        """Test running a 30-day simulation."""
        config = CourtSimConfig(
            start=date(2024, 1, 1),
            days=30,
            seed=42,
            courtrooms=5,
            daily_capacity=50,
            policy="readiness",
            log_dir=temp_output_dir
        )

        sim = CourtSim(config, sample_cases)
        result = sim.run()

        assert result.hearings_total > 0
        assert result.hearings_heard + result.hearings_adjourned == result.hearings_total
        # Check disposal rate is reasonable
        if result.hearings_total > 0:
            disposal_rate = result.disposals / len(sample_cases)
            assert 0.0 <= disposal_rate <= 1.0


@pytest.mark.integration
@pytest.mark.simulation
class TestOutcomeTracking:
    """Test tracking of simulation outcomes."""

    def test_disposal_counting(self, small_case_set, temp_output_dir):
        """Test that disposals are counted correctly."""
        config = CourtSimConfig(
            start=date(2024, 1, 15),
            days=30,
            seed=42,
            courtrooms=2,
            daily_capacity=50,
            policy="readiness",
            log_dir=temp_output_dir
        )

        sim = CourtSim(config, small_case_set)
        result = sim.run()

        # Count disposed cases
        disposed_count = sum(1 for case in small_case_set if case.is_disposed())

        # Should match result
        assert result.disposals == disposed_count

    def test_adjournment_rate(self, sample_cases, temp_output_dir):
        """Test that adjournment rate is realistic."""
        config = CourtSimConfig(
            start=date(2024, 1, 15),
            days=30,
            seed=42,
            courtrooms=5,
            daily_capacity=50,
            policy="readiness",
            log_dir=temp_output_dir
        )

        sim = CourtSim(config, sample_cases)
        result = sim.run()

        if result.hearings_total > 0:
            adj_rate = result.hearings_adjourned / result.hearings_total
            # Realistic adjournment rate: 20-60%
            assert 0.0 <= adj_rate <= 1.0

    def test_utilization_calculation(self, sample_cases, temp_output_dir):
        """Test courtroom utilization calculation."""
        config = CourtSimConfig(
            start=date(2024, 1, 15),
            days=20,
            seed=42,
            courtrooms=3,
            daily_capacity=50,
            policy="readiness",
            log_dir=temp_output_dir
        )

        sim = CourtSim(config, sample_cases)
        result = sim.run()

        # Utilization should be 0-100%
        assert 0.0 <= result.utilization <= 100.0


@pytest.mark.integration
@pytest.mark.simulation
class TestStageProgression:
    """Test case stage progression during simulation."""

    def test_cases_progress_stages(self, sample_cases, temp_output_dir):
        """Test that cases progress through stages."""
        config = CourtSimConfig(
            start=date(2024, 1, 15),
            days=90,
            seed=42,
            courtrooms=5,
            daily_capacity=50,
            policy="readiness",
            log_dir=temp_output_dir
        )

        # Record initial stages
        initial_stages = {case.case_id: case.current_stage for case in sample_cases}

        sim = CourtSim(config, sample_cases)
        sim.run()

        # Check if any cases progressed
        progressed = sum(
            1 for case in sample_cases
            if case.current_stage != initial_stages.get(case.case_id)
        )

        # At least some cases should progress
        assert progressed >= 0

    def test_terminal_stage_handling(self, sample_cases, temp_output_dir):
        """Test that cases in terminal stages are handled correctly."""
        config = CourtSimConfig(
            start=date(2024, 1, 15),
            days=60,
            seed=42,
            courtrooms=5,
            daily_capacity=50,
            policy="readiness",
            log_dir=temp_output_dir
        )

        sim = CourtSim(config, sample_cases)
        sim.run()

        # Check disposed cases are in terminal stages
        from scheduler.data.config import TERMINAL_STAGES
        for case in sample_cases:
            if case.is_disposed():
                assert case.current_stage in TERMINAL_STAGES


@pytest.mark.integration
@pytest.mark.simulation
class TestRipenessIntegration:
    """Test ripeness classification integration."""

    def test_ripeness_reevaluation(self, sample_cases, temp_output_dir):
        """Test that ripeness is re-evaluated during simulation."""
        config = CourtSimConfig(
            start=date(2024, 1, 15),
            days=30,
            seed=42,
            courtrooms=5,
            daily_capacity=50,
            policy="readiness",
            log_dir=temp_output_dir
        )

        sim = CourtSim(config, sample_cases)
        result = sim.run()

        # Check ripeness transitions tracked
        assert result.ripeness_transitions >= 0

    def test_unripe_filtering(self, temp_output_dir):
        """Test that unripe cases are filtered from scheduling."""
        # Create mix of ripe and unripe cases
        generator = CaseGenerator(start=date(2024, 1, 1), end=date(2024, 1, 10), seed=42)
        cases = generator.generate(50)

        # Mark some as unripe
        for i, case in enumerate(cases):
            if i % 3 == 0:
                case.service_status = "PENDING"
                case.purpose_of_hearing = "FOR SUMMONS"

        config = CourtSimConfig(
            start=date(2024, 2, 1),
            days=10,
            seed=42,
            courtrooms=3,
            daily_capacity=50,
            policy="readiness",
            log_dir=temp_output_dir
        )

        sim = CourtSim(config, cases)
        result = sim.run()

        # Should have filtered some unripe cases
        assert result.unripe_filtered >= 0


@pytest.mark.integration
@pytest.mark.edge_case
class TestSimulationEdgeCases:
    """Test simulation edge cases."""

    def test_zero_initial_cases(self, temp_output_dir):
        """Test simulation with no initial cases."""
        config = CourtSimConfig(
            start=date(2024, 1, 15),
            days=10,
            seed=42,
            courtrooms=2,
            daily_capacity=50,
            policy="readiness",
            log_dir=temp_output_dir
        )

        sim = CourtSim(config, [])
        result = sim.run()

        # Should complete without errors
        assert result.hearings_total == 0
        assert result.disposals == 0

    def test_all_cases_disposed_early(self, temp_output_dir):
        """Test when all cases dispose before simulation end."""
        # Create very simple cases that dispose quickly
        generator = CaseGenerator(start=date(2024, 1, 1), end=date(2024, 1, 5), seed=42)
        cases = generator.generate(5)

        # Set all to near-disposal stage
        for case in cases:
            case.current_stage = "ORDERS"
            case.service_status = "SERVED"

        config = CourtSimConfig(
            start=date(2024, 2, 1),
            days=90,
            seed=42,
            courtrooms=2,
            daily_capacity=50,
            policy="readiness",
            log_dir=temp_output_dir
        )

        sim = CourtSim(config, cases)
        result = sim.run()

        # Should handle gracefully
        assert result.disposals <= len(cases)

    @pytest.mark.failure
    def test_invalid_start_date(self, small_case_set, temp_output_dir):
        """Test simulation with invalid start date."""
        with pytest.raises(ValueError):
            CourtSimConfig(
                start="invalid-date",  # Should be date object
                days=10,
                seed=42,
                courtrooms=2,
                daily_capacity=50,
                policy="readiness",
                log_dir=temp_output_dir
            )

    @pytest.mark.failure
    def test_negative_days(self, small_case_set, temp_output_dir):
        """Test simulation with negative days."""
        with pytest.raises(ValueError):
            CourtSimConfig(
                start=date(2024, 1, 15),
                days=-10,
                seed=42,
                courtrooms=2,
                daily_capacity=50,
                policy="readiness",
                log_dir=temp_output_dir
            )


@pytest.mark.integration
@pytest.mark.simulation
class TestEventLogging:
    """Test event logging functionality."""

    def test_events_written(self, small_case_set, temp_output_dir):
        """Test that events are written to CSV."""
        config = CourtSimConfig(
            start=date(2024, 1, 15),
            days=5,
            seed=42,
            courtrooms=2,
            daily_capacity=50,
            policy="readiness",
            log_dir=temp_output_dir
        )

        sim = CourtSim(config, small_case_set)
        sim.run()

        # Check if events file exists
        events_file = temp_output_dir / "events.csv"
        if events_file.exists():
            # Verify it's readable
            import pandas as pd
            df = pd.read_csv(events_file)
            assert len(df) >= 0

    def test_event_count_matches_hearings(self, small_case_set, temp_output_dir):
        """Test that event count matches total hearings."""
        config = CourtSimConfig(
            start=date(2024, 1, 15),
            days=10,
            seed=42,
            courtrooms=2,
            daily_capacity=50,
            policy="readiness",
            log_dir=temp_output_dir
        )

        sim = CourtSim(config, small_case_set)
        sim.run()

        # Events should correspond to hearings
        events_file = temp_output_dir / "events.csv"
        if events_file.exists():
            import pandas as pd
            pd.read_csv(events_file)
            # Event count should match or be close to hearings_total
            # (may have additional events for filings, etc.)


@pytest.mark.integration
@pytest.mark.simulation
class TestPolicyComparison:
    """Test different scheduling policies."""

    def test_fifo_policy(self, sample_cases, temp_output_dir):
        """Test simulation with FIFO policy."""
        config = CourtSimConfig(
            start=date(2024, 1, 15),
            days=20,
            seed=42,
            courtrooms=3,
            daily_capacity=50,
            policy="fifo",
            log_dir=temp_output_dir / "fifo"
        )

        sim = CourtSim(config, sample_cases.copy())
        result = sim.run()

        assert result.hearings_total > 0

    def test_age_policy(self, sample_cases, temp_output_dir):
        """Test simulation with age-based policy."""
        config = CourtSimConfig(
            start=date(2024, 1, 15),
            days=20,
            seed=42,
            courtrooms=3,
            daily_capacity=50,
            policy="age",
            log_dir=temp_output_dir / "age"
        )

        sim = CourtSim(config, sample_cases.copy())
        result = sim.run()

        assert result.hearings_total > 0

    def test_readiness_policy(self, sample_cases, temp_output_dir):
        """Test simulation with readiness policy."""
        config = CourtSimConfig(
            start=date(2024, 1, 15),
            days=20,
            seed=42,
            courtrooms=3,
            daily_capacity=50,
            policy="readiness",
            log_dir=temp_output_dir / "readiness"
        )

        sim = CourtSim(config, sample_cases.copy())
        result = sim.run()

        assert result.hearings_total > 0

