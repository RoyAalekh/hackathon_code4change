### Control Module — Overrides and Explainability

Directory: `scheduler/control/`

This package houses the manual control plane that allows judges or operators to override algorithmic decisions and to inspect the reasoning behind suggestions.

#### Files overview

- `overrides.py`
  - Purpose: Define override types, manage override drafts per cause list, validate changes, and collect judge preferences and audit trails.
  - Key elements:
    - `OverrideType` (Enum): categories like ripeness override, capacity change, add/remove case.
    - `Override`: a single change request with metadata; `to_dict()`, `to_readable_text()` helpers.
    - `JudgePreferences`: persistent preferences per judge; `to_dict()`.
    - `CauseListDraft`: a draft editable list for a given date/courtroom/judge; exposes `get_acceptance_rate()` and `get_modifications_summary()`.
    - `OverrideValidator`: validates requested changes; surface `get_errors()`; targeted validate methods for each override kind (ripeness, capacity, add/remove case).
    - `OverrideManager`: creates drafts, applies overrides, finalizes drafts, fetches preferences, produces statistics, and exports an audit trail.
  - Interactions: Consumed by `core/algorithm.py` to apply judge preferences and manual modifications before final allocation.

- `explainability.py`
  - Purpose: Human‑readable explanations for why cases were selected or not.
  - Typical content: utilities that convert ripeness/eligibility checks and policy scores into readable reasons for UI display and audit logs.
  - Interactions: Used by dashboard pages and potentially during `SchedulingAlgorithm.schedule_day` explanation generation.
