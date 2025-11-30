"""Test script to validate both gap fixes.

Tests:
1. Gap 1: RL training uses EDA-derived parameters
2. Gap 2: Ripeness feedback loop works
"""

from datetime import date, datetime

from rl.config import RLTrainingConfig
from rl.simple_agent import TabularQAgent
from rl.training import RLTrainingEnvironment, train_agent
from scheduler.core.ripeness import RipenessClassifier, RipenessStatus
from scheduler.data.case_generator import CaseGenerator
from scheduler.data.param_loader import ParameterLoader
from scheduler.monitoring.ripeness_calibrator import RipenessCalibrator
from scheduler.monitoring.ripeness_metrics import RipenessMetrics


def test_gap1_eda_alignment():
    """Test that RL training uses EDA-derived parameters."""
    print("\n" + "=" * 70)
    print("GAP 1: Testing EDA Alignment in RL Training")
    print("=" * 70)

    # Generate test cases
    generator = CaseGenerator(
        start=date(2024, 1, 1),
        end=date(2024, 1, 31),
        seed=42,
    )
    cases = generator.generate(100, stage_mix_auto=True)

    # Create environment with param_loader
    env = RLTrainingEnvironment(
        cases=cases,
        start_date=date(2024, 1, 1),
        horizon_days=30,
    )

    # Verify param_loader exists
    assert hasattr(env, 'param_loader'), "Environment should have param_loader"
    assert isinstance(env.param_loader, ParameterLoader), "param_loader should be ParameterLoader instance"

    print("ParameterLoader successfully integrated into RLTrainingEnvironment")

    # Test hearing outcome simulation uses EDA parameters
    test_case = cases[0]
    test_case.current_stage = "ADMISSION"
    test_case.case_type = "RSA"

    # Get EDA-derived adjournment probability
    p_adj_eda = env.param_loader.get_adjournment_prob("ADMISSION", "RSA")
    print(f"EDA adjournment probability for ADMISSION/RSA: {p_adj_eda:.2%}")

    # Simulate outcomes multiple times and check alignment
    outcomes = []
    for _ in range(100):
        outcome = env._simulate_hearing_outcome(test_case)
        outcomes.append(outcome)

    adjourn_rate = sum(1 for o in outcomes if o == "ADJOURNED") / len(outcomes)
    print(f"Simulated adjournment rate: {adjourn_rate:.2%}")
    print(f"  Difference from EDA: {abs(adjourn_rate - p_adj_eda):.2%}")

    # Should be within 15% of EDA value (stochastic sampling)
    assert abs(adjourn_rate - p_adj_eda) < 0.15, f"Adjournment rate {adjourn_rate:.2%} too far from EDA {p_adj_eda:.2%}"

    print("\n✅ GAP 1 FIXED: RL training now uses EDA-derived parameters\n")


def test_gap2_ripeness_feedback():
    """Test that ripeness feedback loop works."""
    print("\n" + "=" * 70)
    print("GAP 2: Testing Ripeness Feedback Loop")
    print("=" * 70)

    # Create metrics tracker
    metrics = RipenessMetrics()

    # Simulate predictions and outcomes (need 50+ for calibrator)
    test_cases = []

    # Pattern: 50% false positives (RIPE but adjourned), 50% false negatives
    for i in range(50):
        if i % 4 == 0:
            test_cases.append((f"case{i}", RipenessStatus.RIPE, False))  # Correct RIPE
        elif i % 4 == 1:
            test_cases.append((f"case{i}", RipenessStatus.RIPE, True))  # False positive
        elif i % 4 == 2:
            test_cases.append((f"case{i}", RipenessStatus.UNRIPE_SUMMONS, True))  # Correct UNRIPE
        else:
            test_cases.append((f"case{i}", RipenessStatus.UNRIPE_SUMMONS, False))  # False negative

    prediction_date = datetime(2024, 1, 1)
    outcome_date = datetime(2024, 1, 2)

    for case_id, predicted_status, was_adjourned in test_cases:
        metrics.record_prediction(case_id, predicted_status, prediction_date)
        actual_outcome = "ADJOURNED" if was_adjourned else "ARGUMENTS"
        metrics.record_outcome(case_id, actual_outcome, was_adjourned, outcome_date)

    print(f"Recorded {len(test_cases)} predictions and outcomes")

    # Get accuracy metrics
    accuracy = metrics.get_accuracy_metrics()
    print("\n  Accuracy Metrics:")
    print(f"    False positive rate: {accuracy['false_positive_rate']:.1%}")
    print(f"    False negative rate: {accuracy['false_negative_rate']:.1%}")
    print(f"    RIPE precision: {accuracy['ripe_precision']:.1%}")
    print(f"    UNRIPE recall: {accuracy['unripe_recall']:.1%}")

    # Expected: 2/4 false positives (50%), 1/2 false negatives (50%)
    assert accuracy['false_positive_rate'] > 0.4, "Should detect false positives"
    assert accuracy['false_negative_rate'] > 0.4, "Should detect false negatives"

    print("\nRipenessMetrics successfully tracks classification accuracy")

    # Test calibrator
    adjustments = RipenessCalibrator.analyze_metrics(metrics)

    print(f"\nRipenessCalibrator generated {len(adjustments)} adjustment suggestions:")
    for adj in adjustments:
        print(f"    - {adj.threshold_name}: {adj.current_value} → {adj.suggested_value}")
        print(f"      Reason: {adj.reason[:80]}...")

    assert len(adjustments) > 0, "Should suggest at least one adjustment"

    # Test threshold configuration
    original_thresholds = RipenessClassifier.get_current_thresholds()
    print(f"\nCurrent thresholds: {original_thresholds}")

    # Apply test adjustment
    test_thresholds = {"MIN_SERVICE_HEARINGS": 2}
    RipenessClassifier.set_thresholds(test_thresholds)

    new_thresholds = RipenessClassifier.get_current_thresholds()
    assert new_thresholds["MIN_SERVICE_HEARINGS"] == 2, "Threshold should be updated"
    print(f"Thresholds successfully updated: {new_thresholds}")

    # Restore original
    RipenessClassifier.set_thresholds(original_thresholds)

    print("\n✅ GAP 2 FIXED: Ripeness feedback loop fully operational\n")


def test_end_to_end():
    """Quick end-to-end test with small training run."""
    print("\n" + "=" * 70)
    print("END-TO-END: Testing Both Gaps Together")
    print("=" * 70)

    # Create agent
    agent = TabularQAgent(learning_rate=0.15, epsilon=0.4, discount=0.95)

    # Minimal training config
    config = RLTrainingConfig(
        episodes=2,
        episode_length_days=10,
        cases_per_episode=50,
        training_seed=42,
    )

    print("Running mini training (2 episodes, 50 cases, 10 days)...")
    stats = train_agent(agent, rl_config=config, verbose=False)

    assert len(stats["episodes"]) == 2, "Should complete 2 episodes"
    assert stats["episodes"][-1] == 1, "Last episode should be episode 1"

    print(f"Training completed: {len(stats['episodes'])} episodes")
    print(f"  Final disposal rate: {stats['disposal_rates'][-1]:.1%}")
    print(f"  States explored: {stats['states_explored'][-1]}")

    print("\n✅ END-TO-END: Both gaps working together successfully\n")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("TESTING GAP FIXES")
    print("=" * 70)

    try:
        test_gap1_eda_alignment()
        test_gap2_ripeness_feedback()
        test_end_to_end()

        print("\n" + "=" * 70)
        print("ALL TESTS PASSED")
        print("=" * 70)
        print("\nSummary:")
        print("  ✅ Gap 1: RL training aligned with EDA parameters")
        print("  ✅ Gap 2: Ripeness feedback loop operational")
        print("  ✅ End-to-end: Both gaps working together")
        print("\nBoth confirmed gaps are now FIXED!")
        print("=" * 70 + "\n")

    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        raise
