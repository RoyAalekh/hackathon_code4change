### Simulation Module — Engine, Allocator, and Policies

Directory: `scheduler/simulation/`

This package provides a discrete‑event simulation of the court scheduling system. It generates synthetic case flows (or consumes real‑like parameters), evaluates scheduling/ripeness policies, and produces quantitative outputs and reports.

#### Files overview

- `engine.py`
  - Purpose: Main simulation loop and state transition engine.
  - Key classes:
    - `CourtSimConfig`: Parameters (capacity, stage transition matrices, adjournment params, filings, horizon, etc.).
    - `CourtSimResult`: Aggregated outputs produced by a run.
    - `CourtSim`: The engine orchestrating daily cycles:
      - `_init_stage_ready()`: initializes stage readiness from configuration.
      - `_evaluate_ripeness(current)`: classify cases using `core.ripeness.RipenessClassifier`.
      - `_choose_cases_for_day(current)`: select candidates (potentially via policies/priority).
      - `_file_new_cases(current, n)`: generate new cases based on expected filings.
      - `_day_process(current)`: core daily loop combining filings, ripeness, scheduling, hearings, adjournments, and disposals.
      - `run()`: iterate over the configured horizon; write metrics and event logs.
  - Interactions: Uses domain models in `scheduler/core/*`, policies in `scheduler/simulation/policies/*`, and allocator.

- `allocator.py`
  - Purpose: Allocate prioritized cases to available courtroom capacity.
  - Typical responsibilities: respect per‑courtroom limits, avoid duplicate bookings, ensure eligibility constraints.
  - Interactions: Invoked by both the simulation engine and the core scheduling algorithm.

- `policies/`
  - Purpose: Pluggable case selection strategies.
  - Files:
    - `age.py`: age‑based prioritization (older cases first, possibly weighted).
    - `fifo.py`: first‑in first‑out ordering respecting readiness.
    - `readiness.py`: prioritization by computed readiness or ripeness score.
  - Interface: Each policy exposes a common callable/signature expected by `engine.py` and the core algorithm’s policy abstraction (`core/policy.py`).

#### Simulation flow (high level)
1) Initialize `CourtSimConfig` from data defaults and parameters.
2) Seed a case population and stage readiness.
3) For each simulated day: file new cases, evaluate ripeness, select cases, allocate to courtrooms, conduct hearings, sample adjournments/next stages/disposals.
4) Persist daily summaries, metrics, and event logs to `outputs/simulation_runs/<version_timestamp>/`.
