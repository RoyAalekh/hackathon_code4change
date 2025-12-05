### Monitoring Module — Ripeness Tracking and Calibration

Directory: `scheduler/monitoring/`

This package provides components to track ripeness prediction outcomes and calibrate thresholds based on observed accuracy. It is currently not wired into the main scheduling flow but is designed for future integration.

#### Files overview

- `ripeness_metrics.py`
  - Purpose: Record per‑case ripeness predictions and later outcomes to compute accuracy statistics and error types.
  - Key elements:
    - `RipenessPrediction` (dataclass): captures `case_id`, `predicted_status`, `prediction_date`, and later the `actual_outcome`, `was_adjourned`, and `outcome_date`.
    - `RipenessMetrics`:
      - `record_prediction(case_id, predicted_status, prediction_date)` — log a prediction when the classifier is invoked.
      - `record_outcome(case_id, actual_outcome, was_adjourned, outcome_date)` — attach ground truth when available.
      - Export utilities to summarize false positives/negatives and overall accuracy; convenience frame exports via pandas.
  - Interactions: Expects callers (e.g., the scheduler) to log predictions and later outcomes; can write CSV summaries for analysis.

- `ripeness_calibrator.py`
  - Purpose: Use aggregated metrics to suggest or set revised ripeness thresholds that improve real‑world performance.
  - Typical responsibilities: fit threshold adjustments to minimize misclassification costs; produce human‑readable calibration reports and recommended parameter deltas consumable by `core/ripeness.py` via `RipenessClassifier.set_thresholds()`.

- `__init__.py`
  - Purpose: Package initialization; may expose convenience imports for metrics/calibration.
