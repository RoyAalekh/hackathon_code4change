### Data Module — Parameters, Defaults, and Case Generation

Directory: `scheduler/data/`

This package is responsible for loading configuration/parameters, exposing default parameter tables, and (optionally) generating synthetic cases. These inputs are used by both the core scheduler and the simulation engine.

#### Files overview

- `config.py`
  - Purpose: Data/config structures and helpers to read configuration (e.g., TOML under `configs/`).
  - Typical contents: typed config models, IO utilities to load/validate values, and a central place to map file paths to parameter tables.
  - Interactions: Consumed by dashboard utilities, simulation runner, and EDA.

- `param_loader.py`
  - Purpose: Load parameter tables required by the scheduler and simulation from CSV/JSON defaults or project artifacts.
  - Inputs (defaults): files under `scheduler/data/defaults/`, including:
    - `adjournment_proxies.csv` — signals/statistics used to approximate adjournment likelihood.
    - `case_type_summary.csv` — frequencies and basic properties by case type.
    - `court_capacity_global.json` — nominal/maximum capacity settings.
    - `stage_duration.csv` — typical durations per stage.
    - `stage_transition_entropy.csv` — transition uncertainty by stage.
    - `stage_transition_probs.csv` — Markov transition probabilities between stages.
  - Outputs: in‑memory DataFrames/objects consumed by `core` and `simulation`.

- `case_generator.py`
  - Purpose: Produce synthetic cases consistent with the parameter distributions for use in simulations or demos.
  - Interactions: Reads parameters via `param_loader.py`; emits `core/Case` instances ready for ripeness evaluation and scheduling.

- `__init__.py`
  - Purpose: Package initialization; may expose convenience imports for loader/generator utilities.

#### Data sources
- Project data: `Data/*.parquet` and derived artifacts in `reports/figures/*` (e.g., cleaned parquet, params CSVs).
- Defaults: `scheduler/data/defaults/*` bundled with the package as fallback/configuration baselines.
