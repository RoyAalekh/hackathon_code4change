# Court Scheduling System - Bug Fixes & Enhancements

## Completed Enhancements

### 2.3 Add Learning Feedback Loop (COMPLETED)
**Status**: Implemented (Dec 2024)
**Solution**:
- Created `RipenessMetrics` class to track predictions vs outcomes
- Created `RipenessCalibrator` with 5 calibration rules
- Added `set_thresholds()` and `get_current_thresholds()` to RipenessClassifier
- Tracks false positive/negative rates, generates confusion matrix
- Suggests threshold adjustments with confidence levels

**Files**:
- scheduler/monitoring/ripeness_metrics.py (254 lines)
- scheduler/monitoring/ripeness_calibrator.py (279 lines)
- scheduler/core/ripeness.py (enhanced with threshold management)

### 4.0.4 Fix RL Reward Computation (COMPLETED)
**Status**: Fixed (Dec 2024)
**Solution**:
- Integrated ParameterLoader into RLTrainingEnvironment
- Replaced hardcoded probabilities (0.7, 0.6, 0.4) with EDA-derived parameters
- Training now uses param_loader.get_adjournment_prob() and param_loader.get_stage_transitions_fast()
- Validation: adjournment rates align within 1% of EDA (43.0% vs 42.3%)

**Files**:
- rl/training.py (enhanced _simulate_hearing_outcome)

---

## Priority 1: Fix State Management Bugs (P0 - Critical)

### 1.1 Fix Override State Pollution
**Problem**: Override flags persist across runs, priority overrides don't clear
**Impact**: Cases keep boosted priority in subsequent schedules

**Solution**:
- Add `clear_overrides()` method to Case class
- Call after each scheduling day or at simulation reset
- Store overrides in separate tracking dict instead of mutating case objects
- Alternative: Use immutable override context passed to scheduler

**Files**:
- scheduler/core/case.py (add clear method)
- scheduler/control/overrides.py (refactor to non-mutating approach)
- scheduler/simulation/engine.py (call clear after scheduling)

### 1.2 Preserve Override Auditability
**Problem**: Invalid overrides removed in-place from input list
**Impact**: Caller loses original override list, can't audit rejections

**Solution**:
- Validate into separate collections: `valid_overrides`, `rejected_overrides`
- Return structured result: `OverrideResult(applied, rejected_with_reasons)`
- Keep original override list immutable
- Log all rejections with clear error messages

**Files**:
- scheduler/control/overrides.py (refactor apply_overrides)
- scheduler/core/algorithm.py (update override handling)

### 1.3 Track Override Outcomes Explicitly
**Problem**: Applied overrides in list, rejected as None in unscheduled
**Impact**: Hard to distinguish "not selected" from "override rejected"

**Solution**:
- Create `OverrideAudit` dataclass: (override_id, status, reason, timestamp)
- Return audit log from schedule_day: `result.override_audit`
- Separate tracking: `cases_not_selected`, `overrides_accepted`, `overrides_rejected`

**Files**:
- scheduler/core/algorithm.py (add audit tracking)
- scheduler/control/overrides.py (structured audit log)

## Priority 2: Strengthen Ripeness Detection (P0 - Critical)

### 2.1 Require Positive Evidence for RIPE
**Problem**: Defaults to RIPE when signals ambiguous
**Impact**: Schedules cases that may not be ready

**Solution**:
- Add `UNKNOWN` status to RipenessStatus enum
- Require explicit RIPE signals: stage progression, document check, age threshold
- Default to UNKNOWN (not RIPE) when data insufficient
- Add confidence score: `ripeness_confidence: float` (0.0-1.0)

**Files**:
- scheduler/core/ripeness.py (add UNKNOWN, confidence scoring)
- scheduler/simulation/engine.py (filter UNKNOWN cases)

### 2.2 Enrich Ripeness Signals
**Problem**: Only uses keyword search and basic stage checks
**Impact**: Misses nuanced bottlenecks

**Solution**:
- Add signals:
    - Filing age relative to case type median
    - Adjournment reason history (recurring "summons pending")
    - Outstanding task list (if available in data)
    - Party/lawyer attendance rate
    - Document submission completeness
- Multi-signal scoring: weighted combination
- Configurable thresholds per signal

**Files**:
- scheduler/core/ripeness.py (add signal extraction)
- scheduler/data/config.py (ripeness thresholds)

### 2.3 Add Learning Feedback Loop (COMPLETED - See top of document)
~~Moved to Completed Enhancements section~~

## Priority 3: Re-enable Simulation Inflow (P1 - High)

### 3.1 Parameterize Case Filing
**Problem**: New filings commented out, no caseload growth
**Impact**: Unrealistic long-term simulations

**Solution**:
- Add `enable_inflow: bool` to CourtSimConfig
- Add `filing_rate_multiplier: float` (default 1.0 for historical rate)
- Expose inflow controls in pipeline config
- Surface inflow metrics in simulation results

**Files**:
- scheduler/simulation/engine.py (uncomment + gate filings)
- court_scheduler_rl.py (add config parameters)

### 3.2 Make Ripeness Re-evaluation Configurable
**Problem**: Fixed 7-day re-evaluation may be too infrequent
**Impact**: Stale classifications drive multiple days

**Solution**:
- Add `ripeness_eval_frequency_days: int` to config (default 7)
- Consider adaptive frequency: more frequent when backlog high
- Log ripeness re-evaluation events

**Files**:
- scheduler/simulation/engine.py (configurable frequency)
- scheduler/data/config.py (add parameter)

## Priority 4: EDA and Configuration Robustness (P1 - High)

### 4.0.1 Fix EDA Memory Issues
**Problem**: EDA converts full Parquet to pandas, risks memory exhaustion
**Impact**: Pipeline fails on large datasets (>50K cases)

**Solution**:
- Add sampling parameter: `eda_sample_size: Optional[int]` (default None = full)
- Stream data instead of loading all at once
- Downcast numeric columns before conversion
- Add memory monitoring and warnings

**Files**:
- src/eda_exploration.py (add sampling)
- src/eda_config.py (memory limits)

### 4.0.2 Fix Headless Rendering
**Problem**: Plotly renderer defaults to "browser", fails in CI/CD
**Impact**: Cannot run EDA in automated pipelines

**Solution**:
- Detect headless environment (check DISPLAY env var)
- Default to "png" or "svg" renderer in headless mode
- Add `--renderer` CLI flag to override

**Files**:
- src/eda_exploration.py (renderer detection)
- court_scheduler_rl.py (add CLI flag)

### 4.0.3 Fix Missing Parameters Fallback
**Problem**: get_latest_params_dir raises when no params exist
**Impact**: Fresh environments can't run simulations

**Solution**:
- Bundle baseline parameters in `scheduler/data/defaults/`
- Fallback to bundled params if no EDA run found
- Add `--use-defaults` flag to force baseline params
- Log warning when using defaults vs EDA-derived

**Files**:
- scheduler/data/config.py (fallback logic)
- scheduler/data/defaults/ (new directory with baseline params)

### 4.0.4 Fix RL Parameter Alignment (COMPLETED - See top of document)
~~Moved to Completed Enhancements section~~

## Priority 5: Enhanced Scheduling Constraints (P2 - Medium)

### 4.1 Judge Blocking & Availability
**Problem**: No per-judge blocked dates
**Impact**: Schedules hearings when judge unavailable

**Solution**:
- Add `blocked_dates: list[date]` to Judge entity
- Add `availability_override: dict[date, bool]` for one-time changes
- Filter eligible courtrooms by judge availability

**Files**:
- scheduler/core/judge.py (add availability fields)
- scheduler/core/algorithm.py (check availability)

### 4.2 Per-Case Gap Overrides
**Problem**: Global MIN_GAP_BETWEEN_HEARINGS, no exceptions
**Impact**: Urgent cases can't be expedited

**Solution**:
- Add `min_gap_override: Optional[int]` to Case
- Apply in eligibility check: `gap = case.min_gap_override or MIN_GAP`
- Track override applications in metrics

**Files**:
- scheduler/core/case.py (add field)
- scheduler/core/algorithm.py (use override in eligibility)

### 4.3 Courtroom Capacity Changes
**Problem**: Fixed daily capacity, no dynamic adjustments
**Impact**: Can't model half-days, special sessions

**Solution**:
- Add `capacity_overrides: dict[date, int]` to Courtroom
- Apply in allocation: check date-specific capacity first
- Support judge preferences (e.g., "Property cases Mondays")

**Files**:
- scheduler/core/courtroom.py (add override dict)
- scheduler/simulation/allocator.py (check overrides)

## Priority 5: Testing & Validation (P1 - High)

### 5.1 Unit Tests for Bug Fixes
**Coverage**:
- Override state clearing
- Ripeness UNKNOWN handling
- Inflow rate calculations
- Constraint validation

**Files**:
- tests/test_overrides.py (new)
- tests/test_ripeness.py (expand)
- tests/test_simulation.py (inflow tests)

### 5.2 Integration Tests
**Scenarios**:
- Full pipeline with overrides applied
- Ripeness transitions over time
- Blocked judge dates respected
- Capacity overrides honored

**Files**:
- tests/integration/test_scheduling_pipeline.py (new)

## Implementation Order

1. **Week 1**: Fix critical bugs
   - State management (1.1, 1.2, 1.3)
   - Configuration robustness (4.0.3 - parameter fallback)
   - Unit tests for above

2. **Week 2**: Strengthen core systems
   - Ripeness detection (2.1, 2.2 - UNKNOWN status, multi-signal)
   - RL reward alignment (4.0.4 - shared reward logic)
   - Re-enable inflow (3.1, 3.2)

3. **Week 3**: Robustness and constraints
   - EDA scaling (4.0.1 - memory management)
   - Headless rendering (4.0.2 - CI/CD compatibility)
   - Enhanced constraints (5.1, 5.2, 5.3)

4. **Week 4**: Testing and polish
   - Comprehensive integration tests
   - Ripeness learning feedback (2.3)
   - All edge cases documented

## Success Criteria

**Bug Fixes**:
- Override state doesn't leak between runs
- All override decisions auditable
- Rejected overrides tracked with reasons

**Ripeness**:
- UNKNOWN status used when confidence low
- False positive rate < 15% (marked RIPE but adjourned)
- Multi-signal scoring operational

**Simulation Realism**:
- Inflow configurable and metrics tracked
- Long runs show realistic caseload patterns
- Ripeness re-evaluation frequency tunable

**Constraints**:
- Judge blocked dates respected 100%
- Per-case gap overrides functional
- Capacity changes applied correctly

**Quality**:
- 90%+ test coverage for bug fixes
- Integration tests pass
- All edge cases documented

## Background

This plan addresses critical bugs and architectural improvements identified through code analysis:

1. **State Management**: Override flags persist across runs, causing silent bias
2. **Ripeness Defaults**: System defaults to RIPE when uncertain, risking premature scheduling
3. **Closed Simulation**: No case inflow, making long-term runs unrealistic
4. **Limited Auditability**: In-place mutations make debugging and QA difficult

See commit history for OutputManager refactoring and Windows compatibility fixes already completed.
