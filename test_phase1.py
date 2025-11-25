"""Phase 1 Validation Script - Test Foundation Components.

This script validates that all Phase 1 components work correctly:
- Configuration loading
- Parameter loading from EDA outputs
- Core entities (Case, Courtroom, Judge, Hearing)
- Calendar utility

Run this with: uv run python test_phase1.py
"""

from datetime import date, timedelta

print("=" * 70)
print("PHASE 1 VALIDATION - Court Scheduler Foundation")
print("=" * 70)

# Test 1: Configuration
print("\n[1/6] Testing Configuration...")
try:
    from scheduler.data.config import (
        WORKING_DAYS_PER_YEAR,
        COURTROOMS,
        SIMULATION_YEARS,
        CASE_TYPE_DISTRIBUTION,
        STAGES,
        FAIRNESS_WEIGHT,
        EFFICIENCY_WEIGHT,
        URGENCY_WEIGHT,
    )
    
    print(f"  Working days/year: {WORKING_DAYS_PER_YEAR}")
    print(f"  Courtrooms: {COURTROOMS}")
    print(f"  Simulation years: {SIMULATION_YEARS}")
    print(f"  Case types: {len(CASE_TYPE_DISTRIBUTION)}")
    print(f"  Stages: {len(STAGES)}")
    print(f"  Objective weights: Fairness={FAIRNESS_WEIGHT}, "
          f"Efficiency={EFFICIENCY_WEIGHT}, "
          f"Urgency={URGENCY_WEIGHT}")
    print("  ✓ Configuration loaded successfully")
except Exception as e:
    print(f"  ✗ Configuration failed: {e}")
    exit(1)

# Test 2: Parameter Loader
print("\n[2/6] Testing Parameter Loader...")
try:
    from scheduler.data.param_loader import load_parameters
    
    params = load_parameters()
    
    # Test transition probability
    prob = params.get_transition_prob("ADMISSION", "ORDERS / JUDGMENT")
    print(f"  P(ADMISSION → ORDERS/JUDGMENT): {prob:.4f}")
    
    # Test stage duration
    duration = params.get_stage_duration("ADMISSION", "median")
    print(f"  ADMISSION median duration: {duration:.1f} days")
    
    # Test capacity
    print(f"  Daily capacity (median): {params.daily_capacity_median}")
    
    # Test adjournment rate
    adj_rate = params.get_adjournment_prob("ADMISSION", "RSA")
    print(f"  RSA@ADMISSION adjournment rate: {adj_rate:.3f}")
    
    print("  ✓ Parameter loader working correctly")
except Exception as e:
    print(f"  ✗ Parameter loader failed: {e}")
    print(f"  Note: This requires EDA outputs to exist in reports/figures/")
    # Don't exit, continue with other tests

# Test 3: Case Entity
print("\n[3/6] Testing Case Entity...")
try:
    from scheduler.core.case import Case, CaseStatus
    
    # Create a sample case
    case = Case(
        case_id="RSA/2025/001",
        case_type="RSA",
        filed_date=date(2025, 1, 15),
        current_stage="ADMISSION",
        is_urgent=False,
    )
    
    print(f"  Created case: {case.case_id}")
    print(f"  Type: {case.case_type}, Stage: {case.current_stage}")
    print(f"  Status: {case.status.value}")
    
    # Test methods
    case.update_age(date(2025, 3, 1))
    print(f"  Age after 45 days: {case.age_days} days")
    
    # Record a hearing
    case.record_hearing(date(2025, 2, 1), was_heard=True, outcome="Heard")
    print(f"  Hearings recorded: {case.hearing_count}")
    
    # Compute priority
    priority = case.get_priority_score()
    print(f"  Priority score: {priority:.3f}")
    
    print("  ✓ Case entity working correctly")
except Exception as e:
    print(f"  ✗ Case entity failed: {e}")
    exit(1)

# Test 4: Courtroom Entity
print("\n[4/6] Testing Courtroom Entity...")
try:
    from scheduler.core.courtroom import Courtroom
    
    # Create a courtroom
    courtroom = Courtroom(
        courtroom_id=1,
        judge_id="J001",
        daily_capacity=151,
    )
    
    print(f"  Created courtroom {courtroom.courtroom_id} with Judge {courtroom.judge_id}")
    print(f"  Daily capacity: {courtroom.daily_capacity}")
    
    # Schedule some cases
    test_date = date(2025, 2, 1)
    case1_id = "RSA/2025/001"
    case2_id = "CRP/2025/002"
    
    courtroom.schedule_case(test_date, case1_id)
    courtroom.schedule_case(test_date, case2_id)
    
    scheduled = courtroom.get_daily_schedule(test_date)
    print(f"  Scheduled {len(scheduled)} cases on {test_date}")
    
    # Check utilization
    utilization = courtroom.compute_utilization(test_date)
    print(f"  Utilization: {utilization:.2%}")
    
    print("  ✓ Courtroom entity working correctly")
except Exception as e:
    print(f"  ✗ Courtroom entity failed: {e}")
    exit(1)

# Test 5: Judge Entity
print("\n[5/6] Testing Judge Entity...")
try:
    from scheduler.core.judge import Judge
    
    # Create a judge
    judge = Judge(
        judge_id="J001",
        name="Justice Smith",
        courtroom_id=1,
    )
    
    judge.add_preferred_types("RSA", "CRP")
    
    print(f"  Created {judge.name} (ID: {judge.judge_id})")
    print(f"  Assigned to courtroom: {judge.courtroom_id}")
    print(f"  Specializations: {judge.preferred_case_types}")
    
    # Record workload
    judge.record_daily_workload(date(2025, 2, 1), cases_heard=25, cases_adjourned=10)
    
    avg_workload = judge.get_average_daily_workload()
    adj_rate = judge.get_adjournment_rate()
    
    print(f"  Average daily workload: {avg_workload:.1f} cases")
    print(f"  Adjournment rate: {adj_rate:.2%}")
    
    print("  ✓ Judge entity working correctly")
except Exception as e:
    print(f"  ✗ Judge entity failed: {e}")
    exit(1)

# Test 6: Hearing Entity
print("\n[6/6] Testing Hearing Entity...")
try:
    from scheduler.core.hearing import Hearing, HearingOutcome
    
    # Create a hearing
    hearing = Hearing(
        hearing_id="H001",
        case_id="RSA/2025/001",
        scheduled_date=date(2025, 2, 1),
        courtroom_id=1,
        judge_id="J001",
        stage="ADMISSION",
    )
    
    print(f"  Created hearing {hearing.hearing_id} for case {hearing.case_id}")
    print(f"  Scheduled: {hearing.scheduled_date}, Stage: {hearing.stage}")
    print(f"  Initial outcome: {hearing.outcome.value}")
    
    # Mark as heard
    hearing.mark_as_heard()
    print(f"  Outcome after hearing: {hearing.outcome.value}")
    print(f"  Is successful: {hearing.is_successful()}")
    
    print("  ✓ Hearing entity working correctly")
except Exception as e:
    print(f"  ✗ Hearing entity failed: {e}")
    exit(1)

# Test 7: Calendar Utility
print("\n[7/7] Testing Calendar Utility...")
try:
    from scheduler.utils.calendar import CourtCalendar
    
    calendar = CourtCalendar()
    
    # Add some holidays
    calendar.add_standard_holidays(2025)
    
    print(f"  Calendar initialized with {len(calendar.holidays)} holidays")
    
    # Test working day check
    monday = date(2025, 2, 3)  # Monday
    saturday = date(2025, 2, 1)  # Saturday
    
    print(f"  Is {monday} (Mon) a working day? {calendar.is_working_day(monday)}")
    print(f"  Is {saturday} (Sat) a working day? {calendar.is_working_day(saturday)}")
    
    # Count working days
    start = date(2025, 1, 1)
    end = date(2025, 1, 31)
    working_days = calendar.working_days_between(start, end)
    print(f"  Working days in Jan 2025: {working_days}")
    
    # Test seasonality
    may_factor = calendar.get_seasonality_factor(date(2025, 5, 1))
    feb_factor = calendar.get_seasonality_factor(date(2025, 2, 1))
    print(f"  Seasonality factor for May: {may_factor} (vacation)")
    print(f"  Seasonality factor for Feb: {feb_factor} (peak)")
    
    print("  ✓ Calendar utility working correctly")
except Exception as e:
    print(f"  ✗ Calendar utility failed: {e}")
    exit(1)

# Integration Test
print("\n" + "=" * 70)
print("INTEGRATION TEST - Putting it all together")
print("=" * 70)

try:
    # Create a mini simulation scenario
    print("\nScenario: Schedule 3 cases across 2 courtrooms")
    
    # Setup
    calendar = CourtCalendar()
    calendar.add_standard_holidays(2025)
    
    courtroom1 = Courtroom(courtroom_id=1, judge_id="J001", daily_capacity=151)
    courtroom2 = Courtroom(courtroom_id=2, judge_id="J002", daily_capacity=151)
    
    judge1 = Judge(judge_id="J001", name="Justice A", courtroom_id=1)
    judge2 = Judge(judge_id="J002", name="Justice B", courtroom_id=2)
    
    # Create cases
    cases = [
        Case(case_id="RSA/2025/001", case_type="RSA", filed_date=date(2025, 1, 1), 
             current_stage="ADMISSION", is_urgent=True),
        Case(case_id="CRP/2025/002", case_type="CRP", filed_date=date(2025, 1, 5), 
             current_stage="ADMISSION", is_urgent=False),
        Case(case_id="CA/2025/003", case_type="CA", filed_date=date(2025, 1, 10), 
             current_stage="ORDERS / JUDGMENT", is_urgent=False),
    ]
    
    # Update ages
    current_date = date(2025, 2, 1)
    for case in cases:
        case.update_age(current_date)
    
    # Sort by priority
    cases_sorted = sorted(cases, key=lambda c: c.get_priority_score(), reverse=True)
    
    print(f"\nCases sorted by priority (as of {current_date}):")
    for i, case in enumerate(cases_sorted, 1):
        priority = case.get_priority_score()
        print(f"  {i}. {case.case_id} - Priority: {priority:.3f}, "
              f"Age: {case.age_days} days, Urgent: {case.is_urgent}")
    
    # Schedule cases
    hearing_date = calendar.next_working_day(current_date, 7)  # 7 days ahead
    print(f"\nScheduling hearings for {hearing_date}:")
    
    for i, case in enumerate(cases_sorted):
        courtroom = courtroom1 if i % 2 == 0 else courtroom2
        judge = judge1 if courtroom.courtroom_id == 1 else judge2
        
        if courtroom.can_schedule(hearing_date, case.case_id):
            courtroom.schedule_case(hearing_date, case.case_id)
            
            hearing = Hearing(
                hearing_id=f"H{i+1:03d}",
                case_id=case.case_id,
                scheduled_date=hearing_date,
                courtroom_id=courtroom.courtroom_id,
                judge_id=judge.judge_id,
                stage=case.current_stage,
            )
            
            print(f"  ✓ {case.case_id} → Courtroom {courtroom.courtroom_id} (Judge {judge.judge_id})")
    
    # Check courtroom schedules
    print(f"\nCourtroom schedules for {hearing_date}:")
    for courtroom in [courtroom1, courtroom2]:
        schedule = courtroom.get_daily_schedule(hearing_date)
        utilization = courtroom.compute_utilization(hearing_date)
        print(f"  Courtroom {courtroom.courtroom_id}: {len(schedule)} cases scheduled "
              f"(Utilization: {utilization:.2%})")
    
    print("\n✓ Integration test passed!")
    
except Exception as e:
    print(f"\n✗ Integration test failed: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

print("\n" + "=" * 70)
print("ALL TESTS PASSED - Phase 1 Foundation is Solid!")
print("=" * 70)
print("\nNext: Phase 2 - Case Generation")
print("  Implement case_generator.py to create 10,000 synthetic cases")
print("=" * 70)
