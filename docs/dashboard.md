### Dashboard Module — Streamlit App and Pages

Directory: `scheduler/dashboard/`

The dashboard provides a Streamlit UI to explore data, inspect the ripeness classifier, run simulations, configure overrides, and view analytics/reports.

#### Files overview

- `app.py`
  - Purpose: Streamlit entrypoint that initializes navigation, shared state, and page routing.
  - Interactions: Uses helpers under `dashboard/utils/` to load data and run simulations; mounts pages under `dashboard/pages/`.

- `__init__.py`
  - Purpose: Package initialization for the dashboard module.

- `pages/1_Data_And_Insights.py`
  - Purpose: Data loading, cleaning summaries, EDA‑style insights and figures.
  - Inputs: parquet/CSV datasets and computed reports in `reports/figures/*`.

- `pages/2_Ripeness_Classifier.py`
  - Purpose: Visualize and test `core.ripeness.RipenessClassifier` on sample cases; display reasons and thresholds.
  - Interactions: Can call into `RipenessClassifier.get_current_thresholds()` and `classify()`.

- `pages/3_Simulation_Workflow.py`
  - Purpose: Configure and run simulation scenarios; display outputs (events, metrics, summaries).
  - Interactions: `dashboard/utils/simulation_runner.py`; backend `scheduler/simulation/engine.py`.

- `pages/4_Cause_Lists_And_Overrides.py`
  - Purpose: Generate draft cause lists for a date; review/apply overrides; export finalized lists.
  - Interactions: `control/overrides.py` for `OverrideManager` and `CauseListDraft`.

- `pages/6_Analytics_And_Reports.py`
  - Purpose: Aggregate analytics, charts, and report downloads; links to `reports/figures/*` and `outputs/simulation_runs/*`.

- `utils/__init__.py`
  - Purpose: Package initialization for dashboard utilities.

- `utils/data_loader.py`
  - Purpose: Load datasets and parameter files for use in the UI; cache artifacts for responsiveness.
  - Inputs: `Data/`, `reports/figures/*/params/*.csv`, and defaults in `scheduler/data/defaults/*`.

- `utils/simulation_runner.py`
  - Purpose: Convenience layer to assemble `CourtSimConfig`, run the simulation, and collect outputs for display/download.
  - Interactions: `scheduler/simulation/engine.py` and policy modules.

- `utils/ui_input_parser.py`
  - Purpose: Parse and validate user inputs from Streamlit widgets into typed configs/overrides.
