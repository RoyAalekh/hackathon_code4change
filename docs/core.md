### Core Module — Domain and Scheduling Algorithm

Directory: `scheduler/core/`

This package defines the domain objects (cases, hearings, courtrooms, judges), the ripeness classifier, policy interfaces, and the main scheduling algorithm that orchestrates daily scheduling.

#### Files overview

- `algorithm.py`
  - Purpose: Implements the daily scheduling pipeline.
  - Key classes:
    - `SchedulingResult`: Aggregates scheduled cases, unscheduled reasons, applied overrides, and explanations.
    - `SchedulingAlgorithm`: Orchestrates the day’s scheduling.
      - `schedule_day(cases, courtrooms, current_date, overrides, preferences, max_explanations_unscheduled)`
        - Flow:
          1) Compute judge preference overrides (if provided).
          2) Filter by ripeness (via `RipenessClassifier`), tracking unscheduled reasons for unripe cases.
          3) Filter eligibility (age gaps, disposed, same‑day constraints) and compute priority.
          4) Apply manual overrides (add/remove cases; capacity changes).
          5) Allocate cases to courtrooms (via allocator interface used in simulation layer).
          6) Generate explanations for unscheduled cases (up to cap) and successful allocations.
        - Inputs: list of `Case`, list of `Courtroom`, `date`, optional `Override` list, optional `JudgePreferences`.
        - Outputs: `SchedulingResult` with scheduled list and explanations.
      - Internal helpers: `_filter_by_ripeness`, `_filter_eligible`, `_get_preference_overrides`, `_apply_manual_overrides`, `_allocate_cases`, `_clear_temporary_case_flags`.
  - Interactions: `core.ripeness`, `control.overrides`, `simulation.allocator`.

- `case.py`
  - Purpose: Core case model and priority logic.
  - Key classes:
    - `CaseStatus`: Enum of lifecycle statuses.
    - `Case`: Fields describe type, stage, history, last hearing, etc.
      - Selected methods: `progress_to_stage`, `record_hearing`, `update_age`, `compute_readiness_score`, `is_ready_for_scheduling`, `needs_alert`, `get_priority_score`, `mark_unripe`, `mark_ripe`, `mark_scheduled`, `is_disposed`, `to_dict`.
  - Interactions: Used by ripeness classifier, scheduler, and simulation.

- `courtroom.py`
  - Purpose: Represents courtroom capacity and scheduling slots.
  - Typical members: courtroom identifier, capacity/availability for a given `date`.
  - Interactions: Allocator consumes courtroom capacity when placing cases.

- `hearing.py`
  - Purpose: Hearing record representation (date, outcome, adjournment, etc.).
  - Interactions: Case history and scheduler eligibility checks (min gap, outcomes).

- `judge.py`
  - Purpose: Judge metadata and optional preference hooks.
  - Interactions: `control.overrides.JudgePreferences` integrates with algorithm preference overrides.

- `policy.py`
  - Purpose: Defines the scheduling policy interface and default implementations for prioritization heuristics.
  - Interactions: Injected into `SchedulingAlgorithm` to determine case ordering.

- `ripeness.py`
  - Purpose: Ripeness classifier and thresholds.
  - Key elements:
    - `RipenessStatus` enum with helpers `is_ripe()` and `is_unripe()`.
    - `RipenessClassifier` with methods:
      - `classify(case, current_date)`: returns `RipenessStatus` and sets reasons.
      - `get_ripeness_priority(case, current_date)`: numeric priority for scheduling.
      - `is_schedulable(case, current_date)`: boolean gate for eligibility.
      - `get_ripeness_reason(status)`: human‑readable reason strings.
      - `estimate_ripening_time(case, current_date)`: expected time until ready.
      - `set_thresholds(new_thresholds)`, `get_current_thresholds()`.
  - Interactions: Used both by `algorithm.py` and the simulation engine.

#### Core flow (within `SchedulingAlgorithm.schedule_day`)
1) Collect inputs (cases, courtrooms, date, optional overrides/preferences).  
2) Ripeness filter: mark unripe with reasons; compute ripeness‑based priority.  
3) Eligibility filter: ensure min gap since last hearing, exclude disposed, enforce capacity constraints.  
4) Apply overrides (manual changes and judge preferences).  
5) Allocate to courtrooms; finalize schedule.  
6) Produce explanations and a `SchedulingResult`.
