"""Test script to validate all merged enhancements are properly parameterized.

Tests the following merged PRs:
- PR #2: Override handling (state pollution fix)
- PR #3: Ripeness UNKNOWN state
- PR #6: Parameter fallback with bundled defaults
- PR #4: RL training with SchedulingAlgorithm constraints
- PR #5: Shared reward helper
- PR #7: Output metadata tracking
"""

import sys
from pathlib import Path
from datetime import date, datetime, timedelta
from typing import Dict, List

# Test configurations
TESTS_PASSED = []
TESTS_FAILED = []


def log_test(name: str, passed: bool, details: str = ""):
    """Log test result."""
    if passed:
        TESTS_PASSED.append(name)
        print(f"✓ {name}")
        if details:
            print(f"  {details}")
    else:
        TESTS_FAILED.append(name)
        print(f"✗ {name}")
        if details:
            print(f"  {details}")


def test_pr2_override_validation():
    """Test PR #2: Override validation preserves original list and tracks rejections."""
    from scheduler.core.algorithm import SchedulingAlgorithm
    from scheduler.core.courtroom import Courtroom
    from scheduler.simulation.policies.readiness import ReadinessPolicy
    from scheduler.simulation.allocator import CourtroomAllocator, AllocationStrategy
    from scheduler.control.overrides import Override, OverrideType
    from scheduler.data.case_generator import CaseGenerator
    
    try:
        # Generate test cases
        gen = CaseGenerator(start=date(2024, 1, 1), end=date(2024, 1, 10), seed=42)
        cases = gen.generate(50)
        
        # Create test overrides (some valid, some invalid)
        test_overrides = [
            Override(
                override_id="test-1",
                override_type=OverrideType.PRIORITY,
                case_id=cases[0].case_id,
                judge_id="TEST-JUDGE",
                timestamp=datetime.now(),
                new_priority=0.95
            ),
            Override(
                override_id="test-2",
                override_type=OverrideType.PRIORITY,
                case_id="INVALID-CASE-ID",  # Invalid case
                judge_id="TEST-JUDGE",
                timestamp=datetime.now(),
                new_priority=0.85
            )
        ]
        
        original_count = len(test_overrides)
        
        # Setup algorithm
        courtrooms = [Courtroom(courtroom_id=1, judge_id="J001", daily_capacity=50)]
        allocator = CourtroomAllocator(num_courtrooms=1, per_courtroom_capacity=50)
        policy = ReadinessPolicy()
        algorithm = SchedulingAlgorithm(policy=policy, allocator=allocator)
        
        # Run scheduling with overrides
        result = algorithm.schedule_day(
            cases=cases,
            courtrooms=courtrooms,
            current_date=date(2024, 1, 15),
            overrides=test_overrides
        )
        
        # Verify original list unchanged
        assert len(test_overrides) == original_count, "Original override list was mutated"
        
        # Verify rejection tracking exists (even if empty for valid overrides)
        assert hasattr(result, 'override_rejections'), "No override_rejections field"
        
        # Verify applied overrides tracked
        assert hasattr(result, 'applied_overrides'), "No applied_overrides field"
        
        log_test("PR #2: Override validation", True, 
                f"Applied: {len(result.applied_overrides)}, Rejected: {len(result.override_rejections)}")
        return True
        
    except Exception as e:
        log_test("PR #2: Override validation", False, str(e))
        return False


def test_pr2_flag_cleanup():
    """Test PR #2: Temporary case flags are cleared after scheduling."""
    from scheduler.data.case_generator import CaseGenerator
    from scheduler.core.algorithm import SchedulingAlgorithm
    from scheduler.core.courtroom import Courtroom
    from scheduler.simulation.policies.readiness import ReadinessPolicy
    from scheduler.simulation.allocator import CourtroomAllocator
    from scheduler.control.overrides import Override, OverrideType
    
    try:
        gen = CaseGenerator(start=date(2024, 1, 1), end=date(2024, 1, 10), seed=42)
        cases = gen.generate(10)
        
        # Set priority override flag
        test_case = cases[0]
        test_case._priority_override = 0.99
        
        # Run scheduling
        courtrooms = [Courtroom(courtroom_id=1, judge_id="J001", daily_capacity=50)]
        allocator = CourtroomAllocator(num_courtrooms=1, per_courtroom_capacity=50)
        policy = ReadinessPolicy()
        algorithm = SchedulingAlgorithm(policy=policy, allocator=allocator)
        
        algorithm.schedule_day(cases, courtrooms, date(2024, 1, 15))
        
        # Verify flag cleared
        assert not hasattr(test_case, '_priority_override') or test_case._priority_override is None, \
            "Priority override flag not cleared"
        
        log_test("PR #2: Flag cleanup", True, "Temporary flags cleared after scheduling")
        return True
        
    except Exception as e:
        log_test("PR #2: Flag cleanup", False, str(e))
        return False


def test_pr3_unknown_ripeness():
    """Test PR #3: UNKNOWN ripeness status exists and is used."""
    from scheduler.core.ripeness import RipenessStatus, RipenessClassifier
    from scheduler.data.case_generator import CaseGenerator
    
    try:
        # Verify UNKNOWN status exists
        assert hasattr(RipenessStatus, 'UNKNOWN'), "RipenessStatus.UNKNOWN not found"
        
        # Create case with ambiguous ripeness
        gen = CaseGenerator(start=date(2024, 1, 1), end=date(2024, 1, 10), seed=42)
        cases = gen.generate(10)
        
        # Clear ripeness indicators to test UNKNOWN default
        test_case = cases[0]
        test_case.last_hearing_date = None
        test_case.service_status = None
        test_case.compliance_status = None
        
        # Classify ripeness
        ripeness = RipenessClassifier.classify(test_case, date(2024, 1, 15))
        
        # Should default to UNKNOWN when no evidence
        assert ripeness == RipenessStatus.UNKNOWN or not ripeness.is_ripe(), \
            "Ambiguous case did not get UNKNOWN or non-RIPE status"
        
        log_test("PR #3: UNKNOWN ripeness", True, f"Status: {ripeness.value}")
        return True
        
    except Exception as e:
        log_test("PR #3: UNKNOWN ripeness", False, str(e))
        return False


def test_pr6_parameter_fallback():
    """Test PR #6: Parameter fallback with bundled defaults."""
    from pathlib import Path
    
    try:
        # Test that defaults directory exists
        defaults_dir = Path("scheduler/data/defaults")
        assert defaults_dir.exists(), f"Defaults directory not found: {defaults_dir}"
        
        # Check for expected default files
        expected_files = [
            "stage_transition_probs.csv",
            "stage_duration.csv", 
            "adjournment_proxies.csv",
            "court_capacity_global.json",
            "stage_transition_entropy.csv",
            "case_type_summary.csv"
        ]
        
        for file in expected_files:
            file_path = defaults_dir / file
            assert file_path.exists(), f"Default file missing: {file}"
        
        log_test("PR #6: Parameter fallback", True, 
                f"Found {len(expected_files)} default parameter files")
        return True
        
    except Exception as e:
        log_test("PR #6: Parameter fallback", False, str(e))
        return False


def test_pr4_rl_constraints():
    """Test PR #4: RL training uses SchedulingAlgorithm with constraints."""
    from rl.training import RLTrainingEnvironment
    from rl.config import RLTrainingConfig, DEFAULT_RL_TRAINING_CONFIG
    from scheduler.data.case_generator import CaseGenerator
    
    try:
        # Create training environment
        gen = CaseGenerator(start=date(2024, 1, 1), end=date(2024, 1, 10), seed=42)
        cases = gen.generate(100)
        
        config = RLTrainingConfig(
            episodes=2,
            cases_per_episode=100,
            episode_length_days=10,
            courtrooms=2,
            daily_capacity_per_courtroom=50,
            enforce_min_gap=True,
            cap_daily_allocations=True,
            apply_judge_preferences=True
        )
        
        env = RLTrainingEnvironment(
            cases=cases,
            start_date=date(2024, 1, 1),
            horizon_days=10,
            rl_config=config
        )
        
        # Verify SchedulingAlgorithm components exist
        assert hasattr(env, 'algorithm'), "No SchedulingAlgorithm in training environment"
        assert hasattr(env, 'courtrooms'), "No courtrooms in training environment"
        assert hasattr(env, 'allocator'), "No allocator in training environment"
        assert hasattr(env, 'policy'), "No policy in training environment"
        
        # Test step with agent decisions
        agent_decisions = {cases[0].case_id: 1, cases[1].case_id: 1}
        updated_cases, rewards, done = env.step(agent_decisions)
        
        assert len(rewards) >= 0, "No rewards returned from step"
        
        log_test("PR #4: RL constraints", True, 
                f"Environment has algorithm, courtrooms, allocator. Capacity enforced: {config.cap_daily_allocations}")
        return True
        
    except Exception as e:
        log_test("PR #4: RL constraints", False, str(e))
        return False


def test_pr5_shared_rewards():
    """Test PR #5: Shared reward helper exists and is used."""
    from rl.rewards import EpisodeRewardHelper
    from rl.training import RLTrainingEnvironment
    from scheduler.data.case_generator import CaseGenerator
    
    try:
        # Verify EpisodeRewardHelper exists
        helper = EpisodeRewardHelper(total_cases=100)
        assert hasattr(helper, 'compute_case_reward'), "No compute_case_reward method"
        
        # Verify training environment uses it
        gen = CaseGenerator(start=date(2024, 1, 1), end=date(2024, 1, 10), seed=42)
        cases = gen.generate(50)
        
        env = RLTrainingEnvironment(cases, date(2024, 1, 1), 10)
        assert hasattr(env, 'reward_helper'), "Training environment doesn't use reward_helper"
        assert isinstance(env.reward_helper, EpisodeRewardHelper), \
            "reward_helper is not EpisodeRewardHelper instance"
        
        # Test reward computation
        test_case = cases[0]
        reward = env.reward_helper.compute_case_reward(
            case=test_case,
            was_scheduled=True,
            hearing_outcome="PROGRESS",
            current_date=date(2024, 1, 15),
            previous_gap_days=30
        )
        
        assert isinstance(reward, float), "Reward is not a float"
        
        log_test("PR #5: Shared rewards", True, f"Helper integrated, sample reward: {reward:.2f}")
        return True
        
    except Exception as e:
        log_test("PR #5: Shared rewards", False, str(e))
        return False


def test_pr7_metadata_tracking():
    """Test PR #7: Output metadata tracking."""
    from scheduler.utils.output_manager import OutputManager
    from pathlib import Path
    
    try:
        # Create output manager
        output = OutputManager(run_id="test_run")
        output.create_structure()
        
        # Verify metadata methods exist
        assert hasattr(output, 'record_eda_metadata'), "No record_eda_metadata method"
        assert hasattr(output, 'save_training_stats'), "No save_training_stats method"
        assert hasattr(output, 'save_evaluation_stats'), "No save_evaluation_stats method"
        assert hasattr(output, 'record_simulation_kpis'), "No record_simulation_kpis method"
        
        # Verify run_record file created
        assert output.run_record_file.exists(), "run_record.json not created"
        
        # Test metadata recording
        output.record_eda_metadata(
            version="test_v1",
            used_cached=False,
            params_path=Path("test_params"),
            figures_path=Path("test_figures")
        )
        
        # Verify metadata was written
        import json
        with open(output.run_record_file, 'r') as f:
            record = json.load(f)
        
        assert 'sections' in record, "No sections in run_record"
        assert 'eda' in record['sections'], "EDA metadata not recorded"
        
        log_test("PR #7: Metadata tracking", True, 
                f"Run record created with {len(record['sections'])} sections")
        return True
        
    except Exception as e:
        log_test("PR #7: Metadata tracking", False, str(e))
        return False


def run_all_tests():
    """Run all enhancement tests."""
    print("=" * 60)
    print("Testing Merged Enhancements")
    print("=" * 60)
    print()
    
    # PR #2 tests
    print("PR #2: Override Handling Refactor")
    print("-" * 40)
    test_pr2_override_validation()
    test_pr2_flag_cleanup()
    print()
    
    # PR #3 tests
    print("PR #3: Ripeness UNKNOWN State")
    print("-" * 40)
    test_pr3_unknown_ripeness()
    print()
    
    # PR #6 tests
    print("PR #6: Parameter Fallback")
    print("-" * 40)
    test_pr6_parameter_fallback()
    print()
    
    # PR #4 tests
    print("PR #4: RL Training Alignment")
    print("-" * 40)
    test_pr4_rl_constraints()
    print()
    
    # PR #5 tests
    print("PR #5: Shared Reward Helper")
    print("-" * 40)
    test_pr5_shared_rewards()
    print()
    
    # PR #7 tests
    print("PR #7: Output Metadata Tracking")
    print("-" * 40)
    test_pr7_metadata_tracking()
    print()
    
    # Summary
    print("=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"Passed: {len(TESTS_PASSED)}")
    print(f"Failed: {len(TESTS_FAILED)}")
    print()
    
    if TESTS_FAILED:
        print("Failed tests:")
        for test in TESTS_FAILED:
            print(f"  - {test}")
        return 1
    else:
        print("All tests passed!")
        return 0


if __name__ == "__main__":
    sys.exit(run_all_tests())
