### Metrics Module — Basic Metrics Utilities

Directory: `scheduler/metrics/`

This package provides lightweight metrics helpers used by simulation runs and analyses.

#### Files overview

- `basic.py`
  - Purpose: Compute aggregate metrics from simulation or scheduling outputs (e.g., throughput, utilization, wait times, adjournment rates).
  - Typical usage: Imported by simulation/reporting code to summarize daily/event logs into CSVs found under `outputs/simulation_runs/*/metrics.csv`.

- `__init__.py`
  - Purpose: Package initialization; may re‑export common helpers.
